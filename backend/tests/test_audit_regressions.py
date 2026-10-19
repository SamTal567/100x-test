"""Focused regression tests verifying fixes for the 19 October audit findings.

Uses disposable SQLite and mocked provider; no live API calls or learner DB modifications.
"""
import pytest
from test_learning_loop import loop, PreparedProvider
from app.db.models import Attempt, CriterionAssessment, Gap, Session
from app.services.reports import check_unprompted


@pytest.mark.asyncio
async def test_baseline_skill_a_unmet_transfer_tests_only_b_does_not_give_criteria_demonstrated(loop):
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()

    # Baseline: Mark memory_lifetime as unmet, save_boundary as met
    crit_a = db.query(CriterionAssessment).join(Attempt).filter(
        Attempt.session_id == session.id,
        Attempt.stage == "diagnostic",
        CriterionAssessment.skill_id == "memory_lifetime"
    ).first()
    if crit_a:
        crit_a.met = False
        crit_a.rating = "not_addressed"

    crit_b = db.query(CriterionAssessment).join(Attempt).filter(
        Attempt.session_id == session.id,
        Attempt.stage == "diagnostic",
        CriterionAssessment.skill_id == "save_boundary"
    ).first()
    if crit_b:
        crit_b.met = True
        crit_b.rating = "demonstrated"
    db.commit()

    # Transfer case tests only save_boundary successfully
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Save boundary demonstrated independently.")
    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Distinguishes saved records from screen state",
            skill_id="save_boundary",
            rating="demonstrated",
            met=True,
            evidence="Saved to DB"
        )
    )
    from copy import deepcopy
    new_snapshot = deepcopy(apply_attempt.case_snapshot)
    new_snapshot["rubric"]["criteria"] = [
        {"criterion": "Distinguishes saved records from screen state", "skill_id": "save_boundary"}
    ]
    apply_attempt.case_snapshot = new_snapshot
    db.commit()

    report = service.generate_report(session)
    # Outcome must NOT be criteria_demonstrated or gap_found since memory_lifetime was simply not rechecked
    assert report.outcome != "criteria_demonstrated"
    assert report.outcome == "inconclusive"
    assert "save boundary" in report.outcome_reason.lower()
    assert "memory lifetime" in report.outcome_reason.lower()
    assert "not rechecked" in report.outcome_reason.lower()
    assert any("memory lifetime" in item.lower() and "not rechecked" in item.lower() for item in report.session_summary["unresolved_summary"].split("; "))

    # Historical baseline ratings must remain preserved
    assert crit_a.met is False
    assert crit_a.rating == "not_addressed"


@pytest.mark.asyncio
async def test_concern_about_a_later_b_succeeds_does_not_mark_gap_addressed(loop):
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()

    diag_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="diagnostic").first()
    # Add gap specifically about memory_lifetime
    gap = Gap(
        session_id=session.id,
        source_attempt_id=diag_attempt.id,
        description="Needs clarification: Explains memory lifetime. State your assumptions.",
        probe_text="How long does memory persist?",
        status="identified"
    )
    db.add(gap)
    db.commit()

    # Later apply attempt tests save_boundary and meets it, but does not test memory_lifetime
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Only save boundary addressed.")
    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Distinguishes saved records from screen state",
            skill_id="save_boundary",
            rating="demonstrated",
            met=True,
            evidence="Saved to DB"
        )
    )
    db.commit()

    report = service.generate_report(session)
    gap_rep = next(g for g in report.gaps if g.id == gap.id)
    # Finding 2: Unrelated positive criterion on save_boundary must NOT mark memory_lifetime gap addressed
    assert gap_rep.addressed_by_attempt_id is None
    assert gap_rep.addressed_stage is None


@pytest.mark.asyncio
async def test_supported_revision_succeeds_independent_transfer_fails_remains_unresolved(loop):
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()

    diag_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="diagnostic").first()
    gap = Gap(
        session_id=session.id,
        source_attempt_id=diag_attempt.id,
        description="Needs clarification: Explains memory lifetime.",
        probe_text="How does memory work?",
        status="identified"
    )
    db.add(gap)
    db.commit()

    # Revision (supported) meets memory_lifetime
    await send(action="request_hint", text="I need a hint")
    await send(action="submit_answer", text="Revised explanation with hint.")
    rev_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="investigate").first()
    rev_attempt.support_level = "supported"
    for row in list(rev_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    rev_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=rev_attempt.id,
            criterion="Explains memory lifetime",
            skill_id="memory_lifetime",
            rating="demonstrated",
            met=True
        )
    )
    db.commit()

    # Independent transfer tests memory_lifetime and FAILS
    await send(action="submit_answer", text="Unfamiliar attempt failing memory lifetime.")
    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    apply_attempt.support_level = "independent"
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Explains memory lifetime",
            skill_id="memory_lifetime",
            rating="not_addressed",
            met=False
        )
    )
    db.commit()

    report = service.generate_report(session)
    gap_rep = next(g for g in report.gaps if g.id == gap.id)
    # Finding 2: Later independent failure means gap must NOT be marked addressed
    assert gap_rep.addressed_by_attempt_id is None
    assert report.outcome == "gap_found"


@pytest.mark.asyncio
async def test_transfer_with_unknown_support_provenance_not_labelled_independent(loop):
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Transfer answer.")

    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    apply_attempt.support_level = "unknown"
    for ca in apply_attempt.criterion_assessments:
        ca.met = True
        ca.rating = "demonstrated"
    db.commit()

    report = service.generate_report(session)
    # Finding 1: Independence must not be claimed if support_level is unknown
    assert "independently" not in report.session_summary["unfamiliar_case_summary"].lower()
    assert "support provenance unknown" in report.session_summary["unfamiliar_case_summary"].lower()
    assert report.final_score is None  # Score compatibility stays null


@pytest.mark.asyncio
async def test_transfer_with_zero_assessment_rows_does_not_claim_demonstrated_zero(loop):
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Transfer answer with no assessment.")

    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    report = service.generate_report(session)
    # Finding 3: Must never output "Demonstrated all 0 criteria independently"
    assert "demonstrated all 0" not in report.session_summary["unfamiliar_case_summary"].lower()
    assert "missing or unavailable" in report.session_summary["unfamiliar_case_summary"].lower()
    assert report.outcome == "inconclusive"


@pytest.mark.asyncio
async def test_technical_failure_is_not_unmet_learner_criterion(loop):
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Transfer answer.")

    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Distinguishes saved records from screen state",
            skill_id="save_boundary",
            rating="technical_failure",
            met=None,
            evidence=None
        )
    )
    db.commit()

    report = service.generate_report(session)
    # Finding 3: Technical failure must not be described as "Remaining unmet"
    assert "remaining unmet" not in report.session_summary["unfamiliar_case_summary"].lower()
    assert "technical failure" in report.session_summary["unfamiliar_case_summary"].lower()
    assert "unmet on unfamiliar case" not in report.session_summary["unresolved_summary"].lower()
    assert "technical failure" in report.session_summary["unresolved_summary"].lower()
    assert report.outcome == "inconclusive"


def test_authored_scenarios_not_falsely_flagged_unprompted():
    # Finding 7: Authored transfer scenarios must not be flagged unprompted
    scenario_5 = (
        "A deployed quiz site builds a JSON settings file containing a long-lived translation-provider secret. "
        "Frontend code fetches the file over HTTPS and calls the provider. The file is not linked in the UI. "
        "Explain the exposure, repair the flow and handle the shipped credential."
    )
    is_unprompted_5, _ = check_unprompted("Handles configuration and exposed keys", "secret_lifecycle", scenario_5, [])
    assert is_unprompted_5 is False

    scenario_6 = (
        "An API correctly calls a paid model from the backend but includes the full outbound Authorization header "
        "in a debug object returned with every result. A student says it is safe because the key was never written "
        "in React source. Evaluate the claim and describe a safe result payload and incident response."
    )
    is_unprompted_6, _ = check_unprompted("Handles configuration and exposed keys", "secret_lifecycle", scenario_6, [])
    assert is_unprompted_6 is False
