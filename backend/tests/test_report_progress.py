import pytest

from app.db.models import CriterionAssessment
from app.services.reports import build_report
from test_current_audit import saved_report  # noqa: F401


def test_initial_omission_is_separate_from_later_independent_evidence(saved_report):
    db, session, attempts, _ = saved_report
    row = attempts[0].criterion_assessments[0]
    row.met, row.rating, row.issue_type = False, 'not_addressed', 'missing_requested_part'
    db.commit()
    summary = build_report(db, session, False).session_summary['personal_summary']
    assert 'boundary' in summary['initial_difficulties'].lower()
    assert 'boundary' in summary['later_evidence'].lower()
    assert 'independently' in summary['later_evidence'].lower()
    assert 'boundary' not in summary['remaining_gaps'].lower()


def test_unrechecked_gap_and_failed_assessment_both_have_next_steps(saved_report):
    db, session, attempts, _ = saved_report
    baseline = attempts[0]
    snapshot = dict(baseline.case_snapshot)
    rubric = dict(snapshot['rubric'])
    rubric['criteria'] = rubric['criteria'] + [
        {'criterion': 'Historical amount', 'skill_id': 'history_reference'},
        {'criterion': 'Unavailable check', 'skill_id': 'unavailable_check'},
    ]
    snapshot['rubric'] = rubric
    baseline.case_snapshot = snapshot
    db.add_all([
        CriterionAssessment(attempt_id=baseline.id, criterion='Historical amount', skill_id='history_reference',
            met=False, rating='partially_demonstrated', evidence=baseline.answer_text),
        CriterionAssessment(attempt_id=baseline.id, criterion='Unavailable check', skill_id='unavailable_check',
            met=None, rating='technical_failure', evidence=''),
    ])
    db.commit()
    summary = build_report(db, session, False).session_summary['personal_summary']
    assert 'history reference' in summary['remaining_gaps'].lower()
    assert any('history reference' in step.lower() and 'case' in step.lower() for step in summary['next_steps'])
    assert any('reassess' in step.lower() for step in summary['next_steps'])
    assert 'unavailable check' not in summary['initial_difficulties'].lower()
    assert 'unavailable' in summary['assessment_notices'].lower()


@pytest.mark.parametrize('support', ['after_teaching', 'unknown'])
def test_supported_or_unknown_transfer_never_clears_independent_recheck(saved_report, support):
    db, session, attempts, _ = saved_report
    row = attempts[0].criterion_assessments[0]
    row.met, row.rating = False, 'partially_demonstrated'
    attempts[1].support_level = support
    db.commit()
    summary = build_report(db, session, False).session_summary['personal_summary']
    assert 'boundary' in summary['remaining_gaps'].lower()
    assert 'independently demonstrated' not in summary['later_evidence'].lower()


def test_failed_transfer_is_not_relabelled_as_a_learner_mistake(saved_report):
    db, session, attempts, _ = saved_report
    row = attempts[1].criterion_assessments[0]
    row.met, row.rating = None, 'technical_failure'
    db.commit()
    summary = build_report(db, session, False).session_summary['personal_summary']
    assert 'unavailable' in summary['assessment_notices'].lower()
    assert 'incorrect' not in summary['remaining_gaps'].lower()
    assert any('reassess' in step.lower() for step in summary['next_steps'])


def test_missing_same_skill_criterion_cannot_clear_initial_difficulty(saved_report):
    db, session, attempts, _ = saved_report
    attempts[0].criterion_assessments[0].met = False
    attempts[0].criterion_assessments[0].rating = 'not_addressed'
    transfer = attempts[1]
    snapshot = dict(transfer.case_snapshot)
    snapshot['rubric'] = dict(snapshot['rubric'])
    snapshot['rubric']['criteria'] = snapshot['rubric']['criteria'] + [
        {'criterion': 'Another boundary requirement', 'skill_id': 'boundary'}]
    transfer.case_snapshot = snapshot
    db.commit()
    summary = build_report(db, session, False).session_summary['personal_summary']
    assert 'boundary' in summary['remaining_gaps']
    assert 'independently demonstrated' not in summary['later_evidence']
    assert summary['assessment_notices']


def test_supported_revision_alone_is_not_independent_improvement(saved_report):
    from app.db.models import Attempt
    db, session, attempts, _ = saved_report
    baseline = attempts[0]
    baseline.criterion_assessments[0].met = False
    baseline.criterion_assessments[0].rating = 'not_addressed'
    attempts[1].criterion_assessments[0].met = False
    attempts[1].criterion_assessments[0].rating = 'partially_demonstrated'
    revision = Attempt(session_id=session.id, case_prompt_id=baseline.case_prompt_id,
        stage='investigate', answer_text=baseline.answer_text, case_snapshot=baseline.case_snapshot,
        support_level='after_teaching', processing_status='complete')
    db.add(revision); db.flush()
    db.add(CriterionAssessment(attempt_id=revision.id, criterion='Boundary', skill_id='boundary',
        met=True, rating='demonstrated', evidence=baseline.answer_text))
    db.commit()
    summary = build_report(db, session, False).session_summary['personal_summary']
    assert 'supported revision' in summary['later_evidence']
    assert 'boundary' in summary['remaining_gaps']
    assert 'does not establish independent learning' in summary['revision_note']
