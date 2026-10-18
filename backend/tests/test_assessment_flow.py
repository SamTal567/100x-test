"""Regression tests for evidence-based conclusions, with isolated records/providers."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base, get_db
from app.db.models import Concept, CasePrompt, Rubric, Attempt, CriterionAssessment, Intervention
from app.seed_data import CONCEPTS, STORAGE_PERSISTENCE_CASES
from app.adapters.openai_adapter import (
    OpenAIAdapter, GapAnalysis, AssessmentResult, CriterionResult,
)
from app.config import Settings, get_settings
import app.services.session_service as service_module


class PreparedAI:
    def __init__(self, gap=False, final_met=True, omit_criteria=False):
        self.gap = gap
        self.final_met = final_met
        self.omit_criteria = omit_criteria

    async def analyse_answer(self, **kwargs):
        return GapAnalysis(
            gap_found=self.gap, description="Possible persistence gap",
            evidence_quote=kwargs["answer"], probe_question="Explain what persists and why.",
        )

    async def assess_attempt(self, **kwargs):
        return AssessmentResult(criteria=[
            CriterionResult(criterion=c["criterion"], met=self.final_met,
                            rating="demonstrated" if self.final_met else "partially_demonstrated",
                            evidence=kwargs["answer"])
            for c in (kwargs["criteria"][:1] if self.omit_criteria else kwargs["criteria"])
        ])


@pytest.fixture
def flow(monkeypatch):
    monkeypatch.setattr(get_settings(), "reviewer_api_key", "fixture-review-key-for-tests")
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    with factory() as db:
        concept = Concept(**deepcopy(CONCEPTS[0]))
        db.add(concept)
        db.flush()
        concept_id = concept.id
        for row in deepcopy(STORAGE_PERSISTENCE_CASES):
            rubric = row.pop("rubric")
            case = CasePrompt(concept_id=concept_id, **row)
            db.add(case)
            db.flush()
            db.add(Rubric(case_prompt_id=case.id, **rubric))
        db.commit()

    def get_test_db():
        with factory() as db:
            yield db

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = get_test_db
    monkeypatch.setattr(service_module, "get_openai_adapter", lambda: PreparedAI())
    client = TestClient(app)
    sid = client.post("/v1/sessions", json={"concept_id": concept_id}).json()["id"]
    sequence = 0

    def send(**kwargs):
        nonlocal sequence
        sequence += 1
        session = client.get(f"/v1/sessions/{sid}").json()
        payload = {"client_turn_id": f"{sid}-{sequence}",
                   "expected_version": session["version"],
                   "prompt_id": session["current_prompt"]["id"],
                   "action": "submit_answer", "text": "My reasoning about persistence."}
        # Exercise selection is separate evidence; these tests isolate conceptual judgments.
        with factory() as db:
            case = db.get(CasePrompt, session["current_prompt"]["id"])
            if case.diagram_preset:
                preset = case.diagram_preset
                payload["diagram_state"] = ({"repair_selection": preset["correct_repair"]}
                    if "correct_repair" in preset else {"blanks": {b["id"]: b["correct"] for b in preset.get("blanks", [])}})
            if case.cloze_preset:
                payload["cloze_state"] = {b["id"]: b["correct"] for b in case.cloze_preset["blanks"]}
        payload.update(kwargs)
        res = client.post(f"/v1/sessions/{sid}/turns", json=payload)
        assert res.status_code == 200, res.text
        return res.json()

    def baseline():
        for _ in range(3):
            response = send()
        return response

    def report():
        return client.get(f"/v1/sessions/{sid}/report").json()

    yield client, sid, send, baseline, report, factory
    client.close()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    engine.dispose()


def test_unanswered_session_is_inconclusive(flow):
    assert flow[4]()["outcome"] == "inconclusive"


def test_unavailable_analysis_never_claims_success(flow, monkeypatch):
    adapter = OpenAIAdapter()
    adapter.settings = Settings(openai_api_key="", _env_file=None)
    monkeypatch.setattr(service_module, "get_openai_adapter", lambda: adapter)
    _, _, send, baseline, report, _ = flow
    result = baseline()
    assert "look solid" not in result["messages"][-1]["content"]
    send()
    evidence = report()
    assert evidence["outcome"] == "inconclusive"
    assert all(c["met"] is None for a in evidence["attempts"] for c in a["criteria"] if not (c.get("skill_id") or "").startswith("exercise:"))
    assert all(len([c for c in a["criteria"] if not (c.get("skill_id") or "").startswith("exercise:")]) == 3 for a in evidence["attempts"])


def test_failed_confirmation_is_not_no_gap(flow, monkeypatch):
    _, _, send, baseline, report, _ = flow
    baseline()
    monkeypatch.setattr(service_module, "get_openai_adapter", lambda: PreparedAI(final_met=False))
    send()
    assert report()["outcome"] == "gap_found"


def test_successful_cases_can_end_without_a_gap(flow):
    _, _, send, baseline, report, _ = flow
    baseline()
    send()
    assert report()["outcome"] == "no_gap"
    assert all(len([c for c in a["criteria"] if not (c.get("skill_id") or "").startswith("exercise:")]) == 3 for a in report()["attempts"])


def test_retry_uses_source_scenario_and_has_criterion_evidence(flow, monkeypatch):
    client, sid, send, baseline, report, factory = flow
    first_id = client.get(f"/v1/sessions/{sid}").json()["current_prompt"]["id"]
    monkeypatch.setattr(service_module, "get_openai_adapter", lambda: PreparedAI(gap=True))
    result = baseline()
    assert result["stage"] == "investigate"
    assert result["current_prompt"]["id"] == first_id
    send(text="Revised reasoning.")
    with factory() as db:
        retry = db.query(Attempt).filter_by(session_id=sid, stage="investigate").one()
        assert retry.case_prompt_id == first_id
        assert retry.rubric_version == 1
    retry_report = next(a for a in report()["attempts"] if a["stage"] == "investigate")
    assert len([c for c in retry_report["criteria"] if not (c.get("skill_id") or "").startswith("exercise:")]) == 3
    assert retry_report["support_level"] == "after_follow_up"


def test_partial_review_does_not_mark_entire_report_reviewed(flow):
    _, sid, send, baseline, report, factory = flow
    baseline()
    send()
    with factory() as db:
        assessment = db.query(CriterionAssessment).join(Attempt).filter(Attempt.session_id == sid).first()
        assessment.status = "reviewed"
        db.commit()
    assert report()["assessment_status"] == "provisional"


def test_all_reviewed_or_corrected_criteria_are_reviewed(flow):
    _, sid, send, baseline, report, factory = flow
    baseline()
    send()
    with factory() as db:
        rows = db.query(CriterionAssessment).join(Attempt).filter(Attempt.session_id == sid).all()
        for row in rows:
            row.status = "corrected"
            row.reviewer_notes = "Checked against the prepared criterion."
        db.commit()
    result = report()
    assert result["assessment_status"] == "reviewed"
    assert result["attempts"][-1]["criteria"][0]["reviewer_notes"]


def test_missing_model_criteria_remain_unclear(flow, monkeypatch):
    monkeypatch.setattr(service_module, "get_openai_adapter", lambda: PreparedAI(omit_criteria=True))
    _, _, send, baseline, report, _ = flow
    baseline()
    send()
    result = report()
    assert result["outcome"] == "inconclusive"
    assert len(result["attempts"][-1]["criteria"]) == 3
    assert sum(c["met"] is None for c in result["attempts"][-1]["criteria"]) == 2


def test_fabricated_criterion_evidence_is_not_accepted(flow, monkeypatch):
    class InventedEvidenceAI(PreparedAI):
        async def assess_attempt(self, **kwargs):
            return AssessmentResult(criteria=[
                CriterionResult(criterion=c["criterion"], met=True, evidence="Words the learner never wrote.")
                for c in kwargs["criteria"]])

    monkeypatch.setattr(service_module, "get_openai_adapter", lambda: InventedEvidenceAI())
    _, _, send, baseline, report, _ = flow
    baseline()
    send()
    result = report()
    assert result["outcome"] == "inconclusive"
    assert all(c["met"] is None for a in result["attempts"] for c in a["criteria"] if not (c.get("skill_id") or "").startswith("exercise:"))


def test_help_is_visible_in_retry_support_level(flow, monkeypatch):
    _, sid, send, baseline, report, factory = flow
    monkeypatch.setattr(service_module, "get_openai_adapter", lambda: PreparedAI(gap=True))
    baseline()
    with factory() as db:
        db.add(Intervention(session_id=sid, intervention_type="resource", title="Persistence explanation"))
        db.commit()
    send()
    retry = next(a for a in report()["attempts"] if a["stage"] == "investigate")
    assert retry["support_level"] == "after_help_offered"


def test_explicit_unclear_review_clears_previous_verdict(flow):
    client, sid, send, baseline, report, factory = flow
    baseline()
    send()
    with factory() as db:
        item = db.query(CriterionAssessment).join(Attempt).filter(Attempt.session_id == sid).first()
        item_id = item.id
        assert item.met is True
    response = client.post(
        f"/v1/review/assessments/{item_id}",
        json={"status": "corrected", "met": None},
        headers={"X-Reviewer-Key": "fixture-review-key-for-tests"},
    )
    assert response.status_code == 200
    assert report()["attempts"][0]["criteria"][0]["met"] is None
    assert report()["outcome"] == "inconclusive"


def test_analysis_error_without_description_is_still_inconclusive(flow, monkeypatch):
    class FailedAnalysisAI(PreparedAI):
        async def analyse_answer(self, **kwargs):
            return GapAnalysis(status="error")

    monkeypatch.setattr(service_module, "get_openai_adapter", lambda: FailedAnalysisAI())
    _, _, send, baseline, report, _ = flow
    baseline()
    send()
    assert report()["outcome"] == "inconclusive"


def test_complete_human_correction_can_reject_a_possible_gap(flow, monkeypatch):
    _, sid, send, baseline, report, factory = flow
    monkeypatch.setattr(service_module, "get_openai_adapter", lambda: PreparedAI(gap=True))
    baseline()
    send()
    send()
    assert report()["outcome"] == "inconclusive"  # Conflicting provisional proposals.
    with factory() as db:
        rows = db.query(CriterionAssessment).join(Attempt).filter(Attempt.session_id == sid).all()
        for row in rows:
            row.status = "corrected"
            row.met = True
        db.commit()
    result = report()
    assert result["assessment_status"] == "reviewed"
    assert result["outcome"] == "no_gap"
    assert result["gaps"]  # Keep the original concern as history.
