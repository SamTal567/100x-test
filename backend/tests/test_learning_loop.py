"""Learning-loop regressions: use disposable SQLite and prepared provider responses."""
from copy import deepcopy

import pytest
import asyncio
import json
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.openai_adapter import OpenAIAdapter, GapAnalysis, AssessmentResult, CriterionResult, TutorResponse
from app.config import Settings
from app.db.database import Base
from app.db.models import Concept, CasePrompt, Rubric, Session, Attempt, CriterionAssessment, Intervention
from app.schemas import TurnRequest
from app.services.session_service import SessionService


class PreparedProvider:
    def __init__(self, gap=True, fail_gap=False, crash=False):
        self.gap, self.fail_gap, self.crash = gap, fail_gap, crash
        self.assess_calls = []

    async def analyse_answer(self, **kwargs):
        if self.crash:
            raise RuntimeError("simulated interrupted processing")
        return GapAnalysis(status="error", description="Invalid quote") if self.fail_gap else GapAnalysis(
            gap_found=self.gap, description="Possible storage uncertainty", evidence_quote=kwargs["answer"],
            probe_question="What changes when this process ends?"
        )

    async def assess_attempt(self, **kwargs):
        self.assess_calls.append(kwargs)
        return AssessmentResult(criteria=[CriterionResult(criterion=c["criterion"], rating="demonstrated",
            met=True, evidence=kwargs["answer"]) for c in kwargs["criteria"]])

    async def tutor_conversation(self, **kwargs):
        return TutorResponse(message="Which step makes that data available after restart?", action_type=kwargs["action"])


@pytest.fixture
def loop():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    db = factory()
    concept = Concept(module="B", slug="storage-test", title="Storage", description="Persistence", enabled=True)
    db.add(concept)
    db.flush()
    cases = []
    for i, (stage, kind, fmt) in enumerate([
        ("diagnostic", "baseline", "diagram_repair"), ("diagnostic", "baseline", "written"),
        ("diagnostic", "baseline", "written"), ("investigate", "practice", "cloze"),
        ("investigate", "practice", "diagram_repair"), ("apply", "transfer", "written"),
        ("apply", "confirmation", "written"), ("apply", "transfer", "written")]):
        case = CasePrompt(concept_id=concept.id, stage=stage, case_type=kind, sort_order=i,
            scenario_text=f"Scenario {i}: a note is kept only in process memory. Explain what survives restart.",
            assumptions=["The process restarts with an empty list."], response_format=fmt,
            diagram_preset={"diagram_id": f"d{i}", "interaction_type": "repair", "nodes": [], "edges": [],
                "repair_options": [{"id": "disk", "label": "Disk", "target_node": "store"},
                                   {"id": "ram", "label": "RAM", "target_node": "memory"}], "correct_repair": "disk"}
                if fmt == "diagram_repair" else None,
            cloze_preset={"cloze_id": "c1", "sentence_template": "A restart clears {{blank1}}.",
                "blanks": [{"id": "blank1", "options": ["memory", "disk"], "correct": "memory"}]}
                if fmt == "cloze" else None)
        db.add(case)
        db.flush()
        db.add(Rubric(case_prompt_id=case.id, reference_answer="Process memory is lost; persist to disk.",
            criteria=[{"criterion": "Explains memory lifetime", "skill_id": "memory_lifetime", "description": "Explains why."}]))
        cases.append(case)
    session = Session(owner_id="learner-1", concept_id=concept.id, current_prompt_id=cases[0].id)
    db.add(session)
    db.commit()
    service = SessionService(db)
    ai = PreparedProvider()
    service.ai = ai
    number = 0

    async def send(**values):
        nonlocal number
        number += 1
        db.refresh(session)
        payload = dict(client_turn_id=f"turn-{number}", expected_version=session.version,
            prompt_id=session.current_prompt_id, action="submit_answer", text="Variables disappear when the process stops.")
        payload.update(values)
        return await service.process_turn(session, TurnRequest(**payload), session.owner_id)

    async def baseline():
        for i in range(3):
            await send(diagram_state={"repair_selection": "disk"} if i == 0 else None)

    yield db, factory, service, session, send, baseline, ai, cases
    db.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_gap_failure_does_not_suppress_criteria_assessment(loop):
    db, _, service, session, _, baseline, ai, _ = loop
    ai.fail_gap = True
    await baseline()
    assert len(ai.assess_calls) == 3
    assert db.query(CriterionAssessment).join(Attempt).filter(Attempt.session_id == session.id,
        CriterionAssessment.criterion == "Explains memory lifetime").count() == 3


@pytest.mark.asyncio
async def test_provider_failure_is_visible_instead_of_successful_stub():
    adapter = OpenAIAdapter()
    adapter.settings = Settings(openai_api_key="", _env_file=None)
    result = await adapter.tutor_conversation("A scenario", [], "My answer", None, None, [], "answer_probe", "Why?")
    assert result.status == "unavailable"
    assert "unavailable" in result.message.lower()
    adapter.settings = Settings(openai_api_key="test-only", _env_file=None)
    adapter._create_completion = lambda **_: (_ for _ in ()).throw(RuntimeError("offline"))
    failed = await adapter.tutor_conversation("A scenario", [], "My answer", None, None, [], "answer_probe", "Why?")
    assert failed.status == "error"


@pytest.mark.asyncio
async def test_real_chat_and_practice_stay_in_investigation(loop):
    db, _, service, session, send, baseline, _, cases = loop
    await baseline()
    for text in ["Why does that happen?", "Does a file behave differently?"]:
        result = await send(action="answer_probe", text=text)
        assert result.stage == "investigate"
    practice = await send(action="request_practice", text=None)
    assert practice.current_prompt.case_type == "practice"
    assert practice.current_prompt.cloze_preset
    result = await send(action="submit_practice", text="Memory is cleared; disk survives.", cloze_state={"blank1": "memory"})
    assert result.stage == "investigate"
    assert result.current_prompt.id == cases[0].id
    assert db.query(Attempt).filter_by(session_id=session.id, stage="practice").count() == 1
    assert db.query(Intervention).filter_by(session_id=session.id, intervention_type="practice").count() == 1
    await send(action="request_teaching", text=None)
    await send(text="The running process loses its variables, but committed disk data can be reloaded.")
    retry = next(a for a in service.generate_report(session).attempts if a.stage == "investigate")
    assert retry.support_level == "after_teaching"
    assert retry.gap_id


@pytest.mark.asyncio
async def test_diagram_is_checked_and_cannot_be_graded_like_another_choice(loop):
    db, _, service, session, send, baseline, _, _ = loop
    await send(diagram_state={"repair_selection": "ram"})
    await send()
    await send()
    report = service.generate_report(session)
    objective = [c for c in report.attempts[0].criteria if c.get("skill_id", "").startswith("exercise:")]
    assert objective and objective[0]["met"] is False
    assert report.attempts[0].diagram_preset


@pytest.mark.asyncio
async def test_finish_and_before_after_report_match_skills(loop):
    _, _, service, session, send, baseline, _, _ = loop
    await baseline()
    await send(action="answer_probe", text="The process ends, so memory disappears.")
    await send(text="The process loses variables. A disk write persists them.")
    result = await send(text="On this different server, stored records can be reloaded.")
    assert result.stage == "completed"
    report = service.generate_report(session)
    compared = next(c for c in report.skill_comparisons if c["skill_id"] == "memory_lifetime")
    assert compared["baseline"] and compared["revision"] and compared["transfer"]
    assert compared["review_status"] == "provisional"


@pytest.mark.asyncio
async def test_explicit_partial_finish_preserves_an_inconclusive_report(loop):
    _, _, service, session, send, _, _, _ = loop
    await send()
    result = await send(action="finish_session", text=None)
    assert result.stage == "completed"
    assert service.generate_report(session).outcome == "inconclusive"


@pytest.mark.asyncio
async def test_interrupt_keeps_latest_answer_and_exact_replay_does_not_duplicate(loop):
    db, _, service, session, send, _, ai, _ = loop
    await send(diagram_state={"repair_selection": "disk"})
    await send()
    ai.crash = True
    payload = TurnRequest(client_turn_id="interrupted", expected_version=session.version,
        prompt_id=session.current_prompt_id, action="submit_answer", text="This last answer must survive.")
    with pytest.raises(RuntimeError):
        await service.process_turn(session, payload, session.owner_id)
    db.rollback()
    assert db.query(Attempt).filter_by(session_id=session.id).count() == 3
    ai.crash = False
    result = await service.process_turn(session, payload, session.owner_id)
    assert result.processing_status == "complete"
    assert db.query(Attempt).filter_by(session_id=session.id).count() == 3


@pytest.mark.asyncio
async def test_wrong_prompt_rejected_before_answer_is_saved(loop):
    db, _, _, session, send, _, _, cases = loop
    with pytest.raises(ValueError, match="prompt"):
        await send(prompt_id=cases[-1].id)
    assert db.query(Attempt).filter_by(session_id=session.id).count() == 0


@pytest.mark.asyncio
async def test_conflicting_provider_rating_cannot_result_in_no_gap(loop):
    _, _, service, session, send, baseline, ai, _ = loop
    ai.gap = False
    original = ai.assess_attempt
    async def contradictory(**kwargs):
        response = await original(**kwargs)
        for row in response.criteria:
            row.rating = "technical_failure"
            row.met = True
        return response
    ai.assess_attempt = contradictory
    await baseline()
    await send()
    assert service.generate_report(session).outcome == "inconclusive"


@pytest.mark.asyncio
async def test_completed_replay_is_owner_checked(loop):
    _, _, service, session, _, _, _, _ = loop
    payload = TurnRequest(client_turn_id="owner-replay", expected_version=session.version,
        prompt_id=session.current_prompt_id, action="submit_answer", text="Process memory ends.")
    await service.process_turn(session, payload, session.owner_id)
    with pytest.raises(ValueError, match="owner"):
        await service.process_turn(session, payload, "a-different-owner")


@pytest.mark.parametrize("state", [{"blanks": []}, {"blanks": None}, {"blanks": "text"}, {"selected_option": "invented"}])
@pytest.mark.asyncio
async def test_malformed_exercise_fields_rejected_before_save(loop, state):
    db, _, _, session, send, _, _, _ = loop
    with pytest.raises(ValueError):
        await send(diagram_state=state)
    assert db.query(Attempt).filter_by(session_id=session.id).count() == 0


@pytest.mark.asyncio
async def test_retry_unavailable_assessments_reuses_saved_answers(loop):
    db, _, service, session, send, baseline, ai, _ = loop
    original = ai.assess_attempt
    async def outage(**kwargs):
        return AssessmentResult(status="error", summary="Temporary outage")
    ai.assess_attempt = outage
    await baseline()
    assert service.generate_report(session).attempts[0].criteria[0]["rating"] == "technical_failure"
    ai.assess_attempt = original
    await send(action="retry_processing", text=None)
    assert db.query(Attempt).filter_by(session_id=session.id).count() == 3
    assert service.generate_report(session).attempts[0].criteria[0]["met"] is True


@pytest.mark.asyncio
async def test_session_scoped_ids_and_stale_preloaded_version(loop):
    db, factory, service, session, send, _, ai, cases = loop
    other = Session(owner_id=session.owner_id, concept_id=session.concept_id, current_prompt_id=cases[0].id)
    db.add(other)
    db.commit()
    payload = TurnRequest(client_turn_id="same-id", expected_version=1, prompt_id=cases[0].id,
        action="submit_answer", text="Process memory ends.")
    await service.process_turn(session, payload, session.owner_id)
    await service.process_turn(other, payload, other.owner_id)
    replay = await service.process_turn(session, payload, session.owner_id)
    assert replay.version == 2
    assert db.query(Attempt).filter_by(session_id=session.id).count() == 1
    await send()
    second_db = factory()
    stale = second_db.get(Session, session.id)
    started, finish = asyncio.Event(), asyncio.Event()
    original = ai.analyse_answer
    async def blocked(**kwargs):
        started.set()
        await finish.wait()
        return await original(**kwargs)
    ai.analyse_answer = blocked
    pending = asyncio.create_task(send())
    await started.wait()
    duplicate = SessionService(second_db)
    duplicate.ai = PreparedProvider()
    try:
        with pytest.raises(ValueError, match="Version mismatch"):
            await duplicate.process_turn(stale, TurnRequest(client_turn_id="stale", expected_version=stale.version,
                prompt_id=stale.current_prompt_id, action="submit_answer", text="Concurrent answer."), stale.owner_id)
    finally:
        finish.set()
        await pending
        second_db.close()
    assert db.query(Attempt).filter_by(session_id=session.id).count() == 3


@pytest.mark.asyncio
async def test_case_snapshot_preserves_original_wording(loop):
    db, _, service, session, send, _, _, cases = loop
    original = cases[0].scenario_text
    await send(diagram_state={"repair_selection": "disk"})
    cases[0].scenario_text = "Changed after the learner answered."
    db.commit()
    assert service.generate_report(session).attempts[0].scenario_text == original


@pytest.mark.asyncio
async def test_partial_finish_can_abandon_failed_processing(loop):
    db, _, service, session, send, _, ai, _ = loop
    await send()
    await send()
    ai.crash = True
    with pytest.raises(RuntimeError):
        await send()
    db.refresh(session)
    assert session.processing_status == "failed"
    result = await send(action="finish_session", text=None)
    assert result.stage == "completed"
    assert db.query(Attempt).filter_by(session_id=session.id).count() == 3
    assert service.generate_report(session).outcome == "inconclusive"


@pytest.mark.asyncio
async def test_raw_contradictory_provider_json_is_not_silently_repaired():
    adapter = OpenAIAdapter()
    adapter.settings = Settings(openai_api_key="test-only", _env_file=None)
    raw = {"criteria": [{"criterion": "Memory", "rating": "not_addressed", "met": True, "evidence": "memory"}]}
    adapter._create_completion = lambda **_: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(raw)))])
    result = await adapter.assess_attempt("Scenario", "memory", "Answer", [{"criterion": "Memory"}])
    assert result.status == "error" or result.criteria[0].rating == "technical_failure"


@pytest.mark.asyncio
async def test_authored_guided_practice_type_is_reachable(loop):
    db, _, _, _, send, baseline, _, cases = loop
    cases[3].case_type = "guided_practice"
    cases[4].case_type = "guided_practice"
    db.commit()
    await baseline()
    result = await send(action="request_practice", text=None)
    assert result.current_prompt.case_type == "guided_practice"
    assert result.practice_active is True


@pytest.mark.asyncio
async def test_omission_gets_neutral_follow_up_without_invented_quote(loop):
    _, _, service, session, _, baseline, ai, _ = loop
    ai.gap = False
    async def omitted(**kwargs):
        return AssessmentResult(criteria=[CriterionResult(criterion=c["criterion"], rating="not_addressed",
            met=False, evidence="Concept not addressed in learner response.") for c in kwargs["criteria"]])
    ai.assess_attempt = omitted
    await baseline()
    assert session.stage == "investigate"
    card = service.get_evidence_cards(session)[0]
    assert not card["evidence_quote"]
    assert card["status"] == "needs_clarification"
    assert "clarif" in card["gap_description"].lower()


@pytest.mark.parametrize("slug", ["storage-persistence", "request-anatomy", "backend-validation", "secret-placement",
    "save-retrieve-display", "entities-attributes", "one-to-many"])
@pytest.mark.asyncio
async def test_real_authored_banks_complete_learning_flow(loop, slug):
    """Production bank shapes and the engine must agree; synthetic grades test wiring only."""
    from app.seed_data.seeding import seed_authored_data
    db, _, _, _, _, _, _, _ = loop
    seed_authored_data(db)
    concept = db.query(Concept).filter_by(slug=slug).one()
    baseline_cases = db.query(CasePrompt).filter_by(concept_id=concept.id, stage="diagnostic", active=True).order_by(CasePrompt.sort_order).all()
    session = Session(owner_id="bank-integration", concept_id=concept.id, current_prompt_id=baseline_cases[0].id)
    db.add(session)
    db.commit()
    service = SessionService(db)
    service.ai = PreparedProvider()
    number = 0
    async def submit(action="submit_answer"):
        nonlocal number
        number += 1
        db.refresh(session)
        case = db.get(CasePrompt, session.current_prompt_id)
        payload = dict(client_turn_id=f"bank-{number}", expected_version=session.version, prompt_id=case.id,
            action=action, text="Fixture reasoning for engine integration." if action.startswith("submit") else None)
        if action.startswith("submit"):
            if case.diagram_preset:
                preset = case.diagram_preset
                payload["diagram_state"] = ({"repair_selection": preset["correct_repair"]} if "correct_repair" in preset
                    else {"blanks": {b["id"]: b["correct"] for b in preset.get("blanks", [])}})
            if case.cloze_preset:
                payload["cloze_state"] = {b["id"]: b["correct"] for b in case.cloze_preset["blanks"]}
        return await service.process_turn(session, TurnRequest(**payload), session.owner_id)
    for case in baseline_cases:
        result = await submit()
    assert result.stage == "investigate"
    formats = set()
    for _ in range(2):
        result = await submit("request_practice")
        assert result.practice_active
        formats.add(result.current_prompt.response_format)
        result = await submit("submit_practice")
        assert result.stage == "investigate" and not result.practice_active
    assert "cloze" in formats and len(formats) == 2
    result = await submit()
    assert result.stage == "apply"
    assert result.current_prompt.id not in {c.id for c in baseline_cases}
    result = await submit()
    assert result.stage == "completed"
    assert service.generate_report(session).skill_comparisons
