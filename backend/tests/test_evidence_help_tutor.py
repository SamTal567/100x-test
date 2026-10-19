"""Evidence/report and teaching regressions: disposable records, no provider calls."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from test_learning_loop import loop, PreparedProvider
from app.adapters.openai_adapter import OpenAIAdapter
from app.config import Settings
from app.db.models import Attempt, Concept, CriterionAssessment, Gap, Intervention
from app.resources import RESOURCE_VERSION
from app.schemas import TurnRequest


@pytest.mark.asyncio
async def test_supported_revision_is_never_a_final_unfamiliar_score(loop):
    _, _, service, session, send, baseline, _, _ = loop
    await baseline()
    await send(action="request_teaching", text="Explain the mechanism.")
    await send(action="submit_answer")
    await send(action="finish_session", text=None)
    report = service.generate_report(session)
    assert report.final_score is None
    assert report.score_change is None
    stages = {item["stage"]: item for item in report.stage_summaries}
    assert stages["revision"]["percentage"] == 100
    assert stages["transfer"]["status"] == "not_assessed"
    assert "growth" not in (report.score_summary or "").lower()


@pytest.mark.asyncio
async def test_uncertain_or_missing_criteria_do_not_become_low_scores(loop):
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    await send(action="continue", text=None)
    await send()
    fresh = db.query(Attempt).filter_by(session_id=session.id, stage="apply").one()
    row = fresh.criterion_assessments[0]
    row.met, row.rating = None, "technical_failure"
    db.commit()
    report = service.generate_report(session)
    assert report.final_score is None
    assert next(a for a in report.attempts if a.id == fresh.id).score is None
    summary = next(s for s in report.stage_summaries if s["stage"] == "transfer")
    assert summary["unavailable_count"] == 1
    assert summary["percentage"] is None
    db.delete(row)
    db.commit()
    report = service.generate_report(session)
    assert report.final_score is None
    summary = next(s for s in report.stage_summaries if s["stage"] == "transfer")
    assert summary["total_count"] == 1 and summary["unavailable_count"] == 1


@pytest.mark.asyncio
async def test_percentages_never_claim_growth_across_different_cases(loop):
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    row = db.query(CriterionAssessment).join(Attempt).filter(Attempt.stage == "diagnostic",
        CriterionAssessment.skill_id == "memory_lifetime").first()
    row.met, row.rating = False, "not_addressed"
    db.commit()
    await send(action="continue", text=None)
    await send()
    report = service.generate_report(session)
    assert report.initial_score == 67 and report.final_score == 100
    assert report.score_change is None
    assert "growth" not in (report.score_summary or "").lower()


@pytest.mark.asyncio
async def test_selection_only_or_legacy_attempt_has_no_conceptual_percentage(loop):
    db, _, service, session, _, baseline, _, _ = loop
    await baseline()
    attempt = db.query(Attempt).filter_by(session_id=session.id, stage="diagnostic").first()
    for row in list(attempt.criterion_assessments):
        if not (row.skill_id or "").startswith("exercise:"):
            db.delete(row)
    db.commit()
    db.expire(attempt, ["criterion_assessments"])
    assert next(a for a in service.generate_report(session).attempts if a.id == attempt.id).score is None
    attempt.case_snapshot = None
    db.commit()
    assert next(a for a in service.generate_report(session).attempts if a.id == attempt.id).score is None


@pytest.mark.asyncio
async def test_guide_open_is_durable_idempotent_and_distinct_from_completion(loop):
    db, _, service, session, send, baseline, _, _ = loop
    db.get(Concept, session.concept_id).slug = "storage-persistence"
    db.commit()
    await baseline()
    request = TurnRequest(client_turn_id="open-guide", expected_version=session.version,
        prompt_id=session.current_prompt_id, action="resource_opened")
    await service.process_turn(session, request, session.owner_id)
    item = db.query(Intervention).filter_by(session_id=session.id, intervention_type="resource").one()
    first_open = item.opened_at
    assert first_open and item.completed_at is None
    assert RESOURCE_VERSION in item.content
    await service.process_turn(session, request, session.owner_id)
    assert db.query(Intervention).filter_by(session_id=session.id, intervention_type="resource").count() == 1
    assert item.opened_at == first_open
    await send(action="resource_completed", resource_id=item.id, text=None)
    assert item.completed_at and item.opened_at == first_open
    await send(action="submit_answer")
    revision = db.query(Attempt).filter_by(session_id=session.id, stage="investigate").one()
    assert revision.support_level == "after_resource"


@pytest.mark.asyncio
async def test_resource_offer_alone_is_not_reading_and_foreign_links_are_rejected(loop):
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    await send(action="request_help", text=None)
    item = db.query(Intervention).filter_by(session_id=session.id, intervention_type="resource").one()
    assert item.opened_at is None and item.completed_at is None
    assert service._support(session, "investigate") == "after_help_offered"
    foreign = Intervention(session_id="another-session", intervention_type="resource", title="Other guide")
    db.add(foreign)
    db.commit()
    with pytest.raises(ValueError, match="session"):
        await send(action="resource_opened", resource_id=foreign.id, text=None)
    with pytest.raises(ValueError, match="guide"):
        await send(action="resource_opened", text="https://example.com/unprepared")


@pytest.mark.asyncio
async def test_opening_legacy_offer_records_actual_material_without_overwriting_old_content(loop):
    db, _, _, session, send, baseline, _, _ = loop
    db.get(Concept, session.concept_id).slug = "storage-persistence"
    await baseline()
    item = Intervention(session_id=session.id, intervention_type="resource", status="delivered",
        title="Old offer", url="/v1/resources/storage-persistence", content="Legacy link-only offer")
    db.add(item)
    db.commit()
    await send(action="resource_opened", resource_id=item.id, text=None)
    assert "Legacy link-only offer" in item.content
    assert f"Opened guide snapshot ({RESOURCE_VERSION})" in item.content


@pytest.mark.asyncio
async def test_later_guide_version_gets_a_new_snapshot_preserving_first_open(loop, monkeypatch):
    from app.services import learning_engine
    db, _, _, session, send, baseline, _, _ = loop
    db.get(Concept, session.concept_id).slug = "storage-persistence"
    await baseline()
    await send(action="resource_opened", text=None)
    item = db.query(Intervention).filter_by(session_id=session.id, intervention_type="resource").one()
    first_open, previous_content = item.opened_at, item.content
    monkeypatch.setattr(learning_engine, "RESOURCE_VERSION", "next-test-version")
    await send(action="resource_opened", resource_id=item.id, text=None)
    assert item.opened_at == first_open
    assert previous_content in item.content
    assert "Opened guide snapshot (next-test-version)" in item.content
    assert item.completed_at is None


@pytest.mark.asyncio
async def test_tutor_receives_frozen_current_material_and_no_held_back_keys(loop):
    db, _, service, session, send, baseline, _, cases = loop
    db.get(Concept, session.concept_id).slug = "storage-persistence"
    criteria = deepcopy(cases[0].rubric.criteria)
    criteria[0]["acceptable_alternatives"] = ["A durable file with an explicit reload is acceptable."]
    cases[0].rubric.criteria = criteria
    original_key = cases[0].rubric.reference_answer
    cases[5].rubric.reference_answer = "HELD_BACK_SENTINEL"
    db.commit()

    class CaptureProvider(PreparedProvider):
        async def tutor_conversation(self, **kwargs):
            self.received = kwargs
            return await super().tutor_conversation(**kwargs)

    provider = CaptureProvider()
    service.ai = provider
    await baseline()
    cases[0].rubric.reference_answer = "MUTATED_KEY_SENTINEL"
    db.commit()
    await send(action="resource_opened", text=None)
    await send(action="answer_probe", text="Would a file and loader be valid?")
    context = provider.received["teaching_context"]
    assert context["reference_answer"] == original_key
    assert context["criteria"][0]["acceptable_alternatives"] == criteria[0]["acceptable_alternatives"]
    assert context["assessments"][0]["rating"] == "demonstrated"
    assert context["lesson"]["version"] == RESOURCE_VERSION
    assert context["help_history"][0]["opened"] is True
    assert "HELD_BACK_SENTINEL" not in json.dumps(provider.received)
    assert "MUTATED_KEY_SENTINEL" not in json.dumps(provider.received)


@pytest.mark.asyncio
async def test_adapter_uses_prepared_context_without_a_live_provider():
    adapter = OpenAIAdapter()
    adapter.settings = Settings(openai_api_key="test-only", _env_file=None)
    captured = {}

    def completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Which completed write survives?"))])

    adapter._create_completion = completion
    context = {"reference_answer": "Prepared storage explanation", "criteria": [{"acceptable_alternatives": ["durable file"]}],
        "lesson": {"version": RESOURCE_VERSION, "paragraphs": ["A completed save survives this restart."]}}
    result = await adapter.tutor_conversation("Scenario", [], "Answer", None, None, [], "answer_probe", "Why?", teaching_context=context)
    assert result.status == "complete"
    prompt = captured["messages"][-1]["content"]
    assert "Prepared storage explanation" in prompt and "durable file" in prompt and RESOURCE_VERSION in prompt


@pytest.mark.asyncio
async def test_practice_tutor_does_not_misattribute_baseline_assessments(loop):
    db, _, service, session, send, baseline, _, cases = loop
    cases[3].rubric.criteria = [{"criterion": "Explains the practice-only recovery step", "skill_id": "recovery_path"}]
    db.commit()

    class CaptureProvider(PreparedProvider):
        async def tutor_conversation(self, **kwargs):
            self.received = kwargs
            return await super().tutor_conversation(**kwargs)

    provider = CaptureProvider()
    service.ai = provider
    await baseline()
    source = db.query(Attempt).filter_by(session_id=session.id, case_prompt_id=cases[0].id).one()
    await send(action="request_practice", text=None)
    await send(action="request_hint", text="Which step should I consider?")
    context = provider.received["teaching_context"]
    assert context["case_id"] == cases[3].id
    assert context["assessments"] == []
    assert context["source_attempt"]["attempt_id"] == source.id
    assert context["source_attempt"]["case_id"] == cases[0].id
    assert context["source_attempt"]["assessments"][0]["criterion"] == "Explains memory lifetime"


@pytest.mark.asyncio
async def test_resolved_shortcomings_give_criteria_demonstrated_and_accurate_headline(loop):
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    # Baseline has an initial shortcoming
    ca = db.query(CriterionAssessment).join(Attempt).filter(
        Attempt.session_id == session.id,
        Attempt.stage == "diagnostic",
        CriterionAssessment.skill_id == "memory_lifetime"
    ).first()
    ca.met = False
    ca.rating = "partially_demonstrated"
    gap_record = db.query(Gap).filter_by(session_id=session.id).first()
    if gap_record:
        gap_record.description = "Uncertainty about memory lifetime"
    db.commit()

    # Learner asks for hint and revises answer
    await send(action="request_hint", text="I need a hint")
    await send(action="submit_answer", text="Revised explanation with storage durability and memory lifetime explained.")
    rev_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="investigate").first()
    for r_ca in rev_attempt.criterion_assessments:
        r_ca.met = True
        r_ca.rating = "demonstrated"
    db.commit()

    # Move to unfamiliar apply case
    await send(action="submit_answer", text="Fresh case application demonstrating storage mechanisms.")
    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    for a_ca in apply_attempt.criterion_assessments:
        a_ca.met = True
        a_ca.rating = "demonstrated"
    db.commit()

    report = service.generate_report(session)
    assert report.outcome == "criteria_demonstrated"
    assert "unfamiliar-case answer demonstrated all" in report.outcome_reason.lower()
    assert "revised answer also addressed" in report.outcome_reason.lower()
    # Check that historical gap is marked as addressed by later evidence
    if report.gaps:
        gap = report.gaps[0]
        assert gap.addressed_by_attempt_id is not None
        assert "revised" in gap.addressed_stage.lower() or "unfamiliar" in gap.addressed_stage.lower()
    # Check session_summary structure
    assert report.session_summary is not None
    assert "demonstrated" in report.session_summary["unfamiliar_case_summary"].lower()


@pytest.mark.asyncio
async def test_unprompted_criterion_is_flagged_without_altering_snapshots(loop):
    db, _, service, session, send, baseline, _, cases = loop
    # Configure case prompt with scenario not mentioning key revocation
    cases[0].scenario_text = "Who can recover the key and draw or describe a request path that keeps this secret backend-only?"
    cases[0].rubric.criteria = [
        {"criterion": "Explains proxy path", "skill_id": "proxy_isolation"},
        {"criterion": "Revokes exposed keys immediately", "skill_id": "secret_lifecycle", "applicability": "unprompted"}
    ]
    db.commit()
    await baseline()
    report = service.generate_report(session)
    # Find the criterion detail in the diagnostic attempt
    diag_attempt = next(a for a in report.attempts if a.stage == "diagnostic")
    unprompted_crit = next((c for c in diag_attempt.criteria if c.get("skill_id") == "secret_lifecycle"), None)
    assert unprompted_crit is not None
    assert unprompted_crit.get("unprompted") is True
    assert "did not explicitly ask" in (unprompted_crit.get("unprompted_note") or "").lower()
