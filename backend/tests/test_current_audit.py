"""Assessment feedback regressions; fictional payloads and disposable SQLite only."""
import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.openai_adapter import OpenAIAdapter, CriterionResult
from app.config import Settings
from app.db.database import Base
from app.db.models import Concept, CasePrompt, Rubric, Session, Attempt, CriterionAssessment
from app.routers.review import review_case, review_assessment
from app.schemas import CaseReviewSubmit, AssessmentReviewSubmit
from app.seed_data import CASE_BANKS
from app.services.evidence import normalized_proposal, snapshot_case
from app.services.reports import build_report


PARTS = [
    {"id": "boundary", "description": "explain the validation boundary", "criteria_names": ["Boundary"]},
    {"id": "write", "description": "explain what may be saved", "criteria_names": ["Write"]},
]
ANSWER = "The server validates direct requests."


def immediate(coroutine):
    """Run a coroutine whose external work is replaced with an immediate response."""
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("Unexpected asynchronous external work")


def assess_payload(monkeypatch, payload):
    adapter = OpenAIAdapter()
    adapter.settings = Settings(openai_api_key="fictional-test", _env_file=None)
    adapter._create_completion = lambda **_: SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=json.dumps(payload)))])
    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)
    monkeypatch.setattr(asyncio, "to_thread", inline)
    return immediate(adapter.assess_attempt("Explain validation and writing.", ANSWER, "Prepared key",
        [{"criterion": "Boundary"}, {"criterion": "Write"}], PARTS))


def test_missing_provider_part_output_is_unavailable_not_learner_omission(monkeypatch):
    result = assess_payload(monkeypatch, {"criteria": []})
    assert all(p.coverage == "unclear" and p.issue_type == "technical_failure"
               for p in result.question_parts_coverage)
    assert all("did not answer" not in (p.explanation or "").lower() for p in result.question_parts_coverage)


@pytest.mark.parametrize("evidence", ["", "invented quote"])
def test_positive_part_feedback_requires_quote_and_discards_unsupported_praise(monkeypatch, evidence):
    result = assess_payload(monkeypatch, {"criteria": [], "question_parts_coverage": [{
        "question_part_id": "boundary", "coverage": "answered", "evidence": evidence,
        "demonstrated_explanation": "You explained everything correctly.", "next_action": "Move on."}]})
    part = result.question_parts_coverage[0]
    assert part.coverage == "unclear" and part.issue_type == "insufficient_evidence"
    assert not part.evidence and not part.demonstrated_explanation
    assert part.next_action != "Move on."


def test_criterion_mapping_uses_authored_names_and_rejects_unrelated_part_id():
    proposal = CriterionResult(criterion="Boundary", rating="demonstrated", met=True,
        evidence=ANSWER, question_part_id="write")
    result = normalized_proposal(proposal, ANSWER, "complete", question_parts=PARTS, criterion_id="Boundary")
    assert result.question_part_id == "boundary"


def test_partial_omission_preserves_demonstrated_reasoning():
    proposal = CriterionResult(criterion="Boundary", rating="partially_demonstrated", met=False,
        evidence=ANSWER, issue_type="missing_requested_part", coverage="partially_answered",
        demonstrated_explanation="You identified the server boundary.", explanation="Explain why clients can bypass checks.")
    result = normalized_proposal(proposal, ANSWER, "complete", question_parts=PARTS, criterion_id="Boundary")
    assert result.rating == "partially_demonstrated" and result.evidence == ANSWER
    assert result.coverage == "partly_answered"


def test_partial_without_issue_type_does_not_establish_an_incorrect_claim():
    proposal = CriterionResult(criterion="Boundary", rating="partially_demonstrated", met=False,
        evidence=ANSWER)
    result = normalized_proposal(proposal, ANSWER, "complete", question_parts=PARTS, criterion_id="Boundary")
    assert result.issue_type == "insufficient_evidence"


def test_unverifiable_criterion_quote_discards_praise_and_improvement_claim():
    proposal = CriterionResult(criterion="Boundary", rating="demonstrated", met=True,
        evidence="invented", demonstrated_explanation="You explained everything correctly.",
        explanation="Fully correct.", next_action="Move on.")
    result = normalized_proposal(proposal, ANSWER, "complete", question_parts=PARTS, criterion_id="Boundary")
    assert result.met is None and not result.evidence and not result.demonstrated_explanation
    assert result.explanation != "Fully correct." and result.next_action != "Move on."


def test_provider_failure_is_not_presented_as_a_learner_quote():
    result = normalized_proposal(None, ANSWER, "error", "Provider failed")
    assert not result.evidence and result.explanation == "Provider failed"


def test_storage_parts_map_to_actual_prepared_criteria():
    for case in CASE_BANKS["storage-persistence"]:
        names = {c["criterion"] for c in case["rubric"]["criteria"]}
        assert all(p["criteria_names"] and set(p["criteria_names"]) <= names for p in case["question_parts"])


@pytest.fixture
def saved_report():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        concept = Concept(module="A", slug="audit", title="Audit", description="Fictional", enabled=True)
        db.add(concept); db.flush()
        cases = []
        for stage in ("diagnostic", "apply"):
            case = CasePrompt(concept_id=concept.id, stage=stage, case_type="baseline" if stage == "diagnostic" else "transfer",
                scenario_text="Explain the server validation boundary.", question_parts=deepcopy(PARTS[:1]))
            db.add(case); db.flush()
            db.add(Rubric(case_prompt_id=case.id, reference_answer=ANSWER,
                criteria=[{"criterion": "Boundary", "skill_id": "boundary"}]))
            db.flush(); cases.append(case)
        session = Session(owner_id="fictional-owner", concept_id=concept.id, stage="completed",
            baseline_prompt_ids=[cases[0].id], baseline_analysis_status="complete")
        db.add(session); db.flush()
        attempts = []
        for case in cases:
            attempt = Attempt(session_id=session.id, case_prompt_id=case.id, stage=case.stage,
                answer_text=ANSWER, case_snapshot=snapshot_case(case), support_level="independent", processing_status="complete")
            db.add(attempt); db.flush()
            db.add(CriterionAssessment(attempt_id=attempt.id, criterion="Boundary", skill_id="boundary",
                rating="demonstrated", met=True, evidence=ANSWER))
            attempts.append(attempt)
        db.commit()
        yield db, session, attempts, cases
    engine.dispose()


@pytest.mark.parametrize("support", ["unknown", "after_teaching"])
def test_personal_summary_respects_transfer_support(saved_report, support):
    db, session, attempts, _ = saved_report
    attempts[1].support_level = support; db.commit()
    summary = build_report(db, session, False).session_summary["personal_summary"]
    assert "independently" not in summary["demonstrated"]
    assert "None. All evaluated skills" not in summary["needs_independent_checking"]


@pytest.mark.parametrize("failure", ["technical_failure", "ambiguous_needs_clarification", "missing"])
def test_personal_summary_does_not_clear_unavailable_or_unclear_transfer(saved_report, failure):
    db, session, attempts, _ = saved_report
    row = attempts[1].criterion_assessments[0]
    if failure == "missing":
        db.delete(row)
    else:
        row.rating, row.met = failure, None
    db.commit()
    summary = build_report(db, session, False).session_summary["personal_summary"]
    assert "None. All evaluated skills" not in summary["needs_independent_checking"]
    assert "Continue to subsequent module" not in summary["recommended_next_step"]


def test_reviewed_case_preserves_question_parts(saved_report):
    db, _, _, cases = saved_report
    original = deepcopy(cases[0].question_parts)
    response = review_case(cases[0].id, CaseReviewSubmit(review_status="reviewed", reviewer_name="Reviewer"), True, db)
    assert db.get(CasePrompt, response["case_id"]).question_parts == original


def test_human_correction_does_not_leave_omission_feedback(saved_report):
    db, _, attempts, _ = saved_report
    row = attempts[1].criterion_assessments[0]
    row.met, row.rating, row.coverage = False, "not_addressed", "unanswered"
    row.issue_type, row.explanation = "missing_requested_part", "You did not answer this part."
    db.commit()
    review_assessment(row.id, AssessmentReviewSubmit(status="corrected", rating="demonstrated",
        reviewer_name="Reviewer", reviewer_notes="The response demonstrates this."), True, db)
    assert row.coverage == "answered" and row.issue_type is None
    assert row.explanation != "You did not answer this part."


def test_human_correction_invalidates_stale_part_coverage_and_preserves_history(saved_report):
    db, _, attempts, _ = saved_report
    row = attempts[1].criterion_assessments[0]
    row.question_part_id = "boundary"
    row.met, row.rating = False, "not_addressed"
    attempts[1].question_parts_coverage = [{"question_part_id": "boundary", "coverage": "unanswered",
        "issue_type": "missing_requested_part", "explanation": "You did not answer this part.", "evidence": ""}]
    db.commit()
    review_assessment(row.id, AssessmentReviewSubmit(status="corrected", rating="demonstrated", reviewer_name="Reviewer"), True, db)
    part = attempts[1].question_parts_coverage[0]
    assert part["coverage"] == "unclear" and part["issue_type"] != "missing_requested_part"
    from app.db.models import AssessmentReviewRevision
    revision = db.query(AssessmentReviewRevision).one()
    assert revision.previous_snapshot["question_parts_coverage"][0]["coverage"] == "unanswered"


def test_case_review_accepts_updated_authored_parts(saved_report):
    db, _, _, cases = saved_report
    parts = [{"id": "new", "description": "explain the updated scenario", "criteria_names": ["Boundary"]}]
    response = review_case(cases[0].id, CaseReviewSubmit(review_status="reviewed", reviewer_name="Reviewer",
        question_parts=parts), True, db)
    assert db.get(CasePrompt, response["case_id"]).question_parts == parts


def test_unavailable_report_concern_does_not_blame_learner(saved_report):
    db, session, attempts, _ = saved_report
    row = attempts[1].criterion_assessments[0]
    row.rating, row.met, row.evidence = "technical_failure", None, "Provider unavailable"
    row.next_action = "Explain the omitted persistence mechanism."
    db.commit()
    card = build_report(db, session, False).session_summary["concern_cards"][0]
    assert card["learner_quote"] == ""
    assert "No accurate reasoning" not in card["what_was_correct"]
    assert "incomplete or ambiguous" not in card["why_rating"]
    assert "reassessment" in card["how_to_improve"].lower()
    assert "reassessment" in card["suggested_next_step"].lower()


def test_legacy_partial_report_concern_is_not_an_incorrect_claim(saved_report):
    db, session, attempts, _ = saved_report
    row = attempts[1].criterion_assessments[0]
    row.rating, row.met, row.issue_type = "partially_demonstrated", False, None
    db.commit()
    card = build_report(db, session, False).session_summary["concern_cards"][0]
    assert card["issue_type"] == "insufficient_evidence"
