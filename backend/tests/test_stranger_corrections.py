"""Fictional reproductions of report/interaction issues, no real learner records."""
import json
from copy import deepcopy
from types import SimpleNamespace
import pytest
from app.adapters.openai_adapter import TutorResponse, CriterionResult, AssessmentResult, OpenAIAdapter
from app.config import Settings
from app.db.models import Gap, Attempt, Intervention
from app.services.reports import build_report
from test_current_audit import saved_report  # noqa: F401
from test_learning_loop import loop, PreparedProvider  # noqa: F401


def test_shared_skill_does_not_clear_a_different_specific_concern(saved_report):
    db, session, attempts, _ = saved_report
    for attempt, criterion in zip(attempts, ['Recognises empty restart state', 'Recovery path repopulates cache']):
        snapshot = deepcopy(attempt.case_snapshot)
        snapshot['rubric']['criteria'] = [{'criterion': criterion, 'skill_id': 'recovery_path'}]
        attempt.case_snapshot = snapshot
        row = attempt.criterion_assessments[0]
        row.criterion, row.skill_id = criterion, 'recovery_path'
    attempts[0].criterion_assessments[0].rating = 'not_addressed'
    attempts[0].criterion_assessments[0].met = False
    gap = Gap(session_id=session.id, source_attempt_id=attempts[0].id,
        description='Needs clarification: Recognises empty restart state.', status='needs_clarification')
    db.add(gap); db.commit()
    report = build_report(db, session, False)
    assert report.gaps[0].addressed_by_attempt_id is None
    assert 'recovery path' in report.session_summary['personal_summary']['remaining_gaps']
    assert 'Recognises empty restart state' in report.session_summary['personal_summary']['remaining_gaps']


@pytest.mark.asyncio
async def test_inconsistent_revision_is_saved_and_clarified_before_transfer(loop):
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    class RevisionProvider(PreparedProvider):
        async def assess_attempt(self, **kwargs):
            return AssessmentResult(criteria=[CriterionResult(criterion=c['criterion'], met=False,
                rating='partially_demonstrated', issue_type='incorrect_claim', evidence=kwargs['answer'])
                for c in kwargs['criteria']])
    service.ai = RevisionProvider()
    response = await send(text='It points to memory after restart.', diagram_state={'repair_selection': 'ram'})
    assert session.stage == 'investigate'
    revision = db.query(Attempt).filter_by(session_id=session.id, stage='investigate').one()
    assert revision.answer_text == 'It points to memory after restart.'
    assert any('inconsistent' in m.content.lower() and 'clarif' in m.content.lower() for m in response.messages)
    report = service.generate_report(session)
    assert 'inconsistent' in report.session_summary['personal_summary']['revision_consistency_note'].lower()
    # The learner can explicitly proceed; no automatic forced remediation loop.
    await send(action='continue', text=None)
    assert session.stage == 'apply'


@pytest.mark.asyncio
async def test_direct_teaching_is_recorded_even_when_requested_as_followup(loop):
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    class TeachingProvider(PreparedProvider):
        async def tutor_conversation(self, **kwargs):
            return TutorResponse(message='Save to disk before acknowledgment.', assistance_kind='teaching')
    service.ai = TeachingProvider()
    await send(action='answer_probe', text='The list is empty.')
    assert db.query(Intervention).filter_by(session_id=session.id, intervention_type='teaching').count() == 1
    assert service._support(session, 'investigate') == 'after_teaching'
    await send()
    assert db.query(Attempt).filter_by(session_id=session.id, stage='investigate').one().support_level == 'after_teaching'


@pytest.mark.asyncio
async def test_unclassified_tutor_content_is_not_claimed_as_hint_only(loop):
    _, _, service, session, send, baseline, _, _ = loop
    await baseline()
    class UnknownProvider(PreparedProvider):
        async def tutor_conversation(self, **kwargs):
            return TutorResponse(message='A legacy response with no assistance metadata.')
    service.ai = UnknownProvider()
    await send(action='request_hint', text=None)
    assert service._support(session, 'investigate') == 'after_help_unknown'


@pytest.mark.asyncio
async def test_tutor_completion_carries_assistance_metadata_in_same_call():
    adapter = OpenAIAdapter(); adapter.settings = Settings(openai_api_key='fictional', _env_file=None)
    captured = []
    def completion(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            'message':'The old process memory is cleared.', 'assistance_kind':'teaching'})))])
    adapter._create_completion = completion
    reply = await adapter.tutor_conversation('Scenario', [], 'Answer', None, None, [], 'answer_probe', 'Why?')
    assert reply.message == 'The old process memory is cleared.'
    assert reply.assistance_kind == 'teaching'
    assert len(captured) == 1 and captured[0]['json_mode']


def test_inconclusive_reason_names_failed_gap_analysis(saved_report):
    db, session, _, _ = saved_report
    session.baseline_analysis_status = 'error';db.commit()
    report=build_report(db,session,False)
    assert 'initial gap analysis' in report.outcome_reason.lower()
    assert 'lack usable assessment evidence' not in report.outcome_reason


@pytest.mark.asyncio
async def test_equivalent_reasoning_guidance_preserves_distinct_criteria():
    adapter=OpenAIAdapter();adapter.settings=Settings(openai_api_key='fictional',_env_file=None)
    captured={}
    answer='The cache reloads the updated 900 value from the database.'
    def completion(**kwargs):
        captured.update(kwargs)
        data={'criteria':[
            {'criterion':'Database supplies current value','met':True,'rating':'demonstrated','evidence':answer},
            {'criterion':'Old cache is lost','met':False,'rating':'not_addressed','evidence':''}]}
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(data)))])
    adapter._create_completion=completion
    result=await adapter.assess_attempt('Explain recovery.',answer,'Prepared key',[
        {'criterion':'Database supplies current value'},{'criterion':'Old cache is lost'}])
    system=captured['messages'][0]['content']
    assert 'Assess the mechanism expressed' in system and 'do not require terms' in system.lower()
    assert result.criteria[0].met is True and result.criteria[1].rating=='not_addressed'


@pytest.mark.asyncio
async def test_failed_tutor_reply_does_not_count_as_delivered_help(loop):
    _, _, service, session, send, baseline, _, _=loop
    await baseline()
    class FailedProvider(PreparedProvider):
        async def tutor_conversation(self, **kwargs):
            return TutorResponse(message='Unavailable',status='error',assistance_kind='teaching')
    service.ai=FailedProvider()
    await send(action='request_hint',text=None)
    assert service._support(session,'investigate')=='after_follow_up'


@pytest.mark.asyncio
async def test_plain_legacy_tutor_reply_remains_unknown():
    adapter=OpenAIAdapter();adapter.settings=Settings(openai_api_key='fictional',_env_file=None)
    adapter._create_completion=lambda **_:SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Which record is read?'))])
    reply=await adapter.tutor_conversation('Scenario',[],'Answer',None,None,[],'request_hint',None)
    assert reply.message=='Which record is read?' and reply.assistance_kind=='unknown'


def test_starting_strengths_are_not_presented_as_new_learning(saved_report):
    db,session,_,_=saved_report
    summary=build_report(db,session,False).session_summary['personal_summary']
    assert summary['starting_strengths']=='Before tutoring, baseline evidence demonstrated: Boundary.'
    assert 'learned' not in summary['starting_strengths']
