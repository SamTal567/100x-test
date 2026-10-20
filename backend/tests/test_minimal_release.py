"""Minimal final fixes using fictional saved evidence and mocked providers only."""
from copy import deepcopy
import pytest
from app.adapters.openai_adapter import CriterionResult
from app.db.models import CriterionAssessment
from app.services.evidence import normalized_proposal
from app.services.reports import build_report
from test_current_audit import saved_report  # noqa: F401
from test_learning_loop import loop, PreparedProvider  # noqa: F401


def test_omission_names_only_missing_criterion_not_whole_answered_part():
    part={'id':'source','description':'Explain which messages survive and why memory is lost',
          'criteria_names':['Database survives','Variable data is lost']}
    result=normalized_proposal(CriterionResult(criterion='Variable data is lost',met=False,rating='not_addressed'),
        'All messages survive in PostgreSQL.','complete',question_parts=[part],criterion_id='Variable data is lost')
    assert 'Variable data is lost' in result.explanation
    assert part['description'] not in result.explanation
    assert result.evidence=='' and result.rating=='not_addressed'


def test_storage_equivalence_accepts_volatile_cache_without_name_identity(saved_report):
    db,session,attempts,_=saved_report
    session.concept.slug='storage-persistence'
    for a,name in zip(attempts,['Identifies memory as volatile','Cache is volatile']):
        snap=deepcopy(a.case_snapshot);snap['rubric']['criteria']=[{'criterion':name,'skill_id':'memory_lifetime'}];a.case_snapshot=snap
        row=a.criterion_assessments[0];row.criterion=name;row.skill_id='memory_lifetime'
    attempts[0].criterion_assessments[0].met=False
    attempts[0].criterion_assessments[0].rating='partially_demonstrated'
    db.commit()
    summary=build_report(db,session,False).session_summary['personal_summary']
    assert 'original requirement not independently rechecked' not in summary['remaining_gaps']
    assert 'No unresolved' in summary['remaining_gaps']


def test_successful_concepts_separate_from_missing_diagram_and_analysis(saved_report):
    db,session,attempts,_=saved_report
    session.baseline_analysis_status='error'
    db.add(CriterionAssessment(attempt_id=attempts[1].id,criterion='Diagram selection',skill_id='exercise:diagram',met=None,rating='not_addressed'))
    db.commit()
    sections=build_report(db,session,False).session_summary['assessment_summary']
    assert '1/1' in sections['conceptual'] and 'independently' in sections['conceptual']
    assert '1 unanswered' in sections['exercises']
    assert 'unavailable' in sections['analysis']
    assert '1/1' in sections['headline']


@pytest.mark.asyncio
async def test_chat_receives_actual_revision_submission_state(loop):
    _,_,service,session,send,baseline,_,_=loop
    class Capture(PreparedProvider):
        async def tutor_conversation(self,**kwargs):
            self.context=kwargs['teaching_context']
            return await super().tutor_conversation(**kwargs)
    service.ai=provider=Capture()
    await baseline();await send(action='answer_probe',text='Here is my revised explanation in chat.')
    state=provider.context['submission_state']
    assert state['current_message_kind']=='conversation_reply'
    assert state['revision_submitted'] is False
    assert state['next_action_label']=='Review and revise my answer'


def test_empty_state_equivalence_requires_both_loss_and_repopulation():
    from app.services.criterion_equivalence import covers_criterion
    rows=[{'criterion':'Recovery path repopulates cache','met':True,'rating':'demonstrated'}]
    assert not covers_criterion('Recognises empty restart state',rows,'storage-persistence')
    rows.append({'criterion':'Cache is volatile','met':True,'rating':'demonstrated'})
    assert covers_criterion('Recognises empty restart state',rows,'storage-persistence')
    assert not covers_criterion('Recognises empty restart state',rows,'different-concept')
    rows[-1]['met']=False;rows[-1]['rating']='partially_demonstrated'
    assert not covers_criterion('Recognises empty restart state',rows,'storage-persistence')


def test_existing_provisional_omission_displays_specific_target_without_rewriting_history(saved_report):
    db,session,attempts,_=saved_report
    row=attempts[0].criterion_assessments[0]
    row.met=False;row.rating='not_addressed';row.explanation='You did not answer the entire question.'
    db.commit()
    report=build_report(db,session,False)
    assert 'specific requirement: Boundary' in report.attempts[0].criteria[0]['explanation']
    assert row.explanation=='You did not answer the entire question.'
