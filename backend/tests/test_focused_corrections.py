"""Focused regression tests demonstrating the 5 issues before and after correction.

Uses disposable SQLite and mocked provider; no live API calls or learner DB modifications.
"""
from copy import deepcopy
import pytest
from test_learning_loop import loop, PreparedProvider
from app.db.models import Attempt, CriterionAssessment, Gap, Session


# ============================================================================
# ISSUE 1: Partially assessed answers still claim all criteria were demonstrated
# ============================================================================

@pytest.mark.asyncio
async def test_issue1_demonstrated_plus_ambiguous(loop):
    """Demonstrated + ambiguous must NOT claim 'Demonstrated all 2 criteria independently'."""
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Transfer answer with mixed demonstrated and ambiguous criteria.")

    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    assert apply_attempt is not None, "Apply attempt must exist"
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    # Two prepared criteria in frozen snapshot:
    snapshot = deepcopy(apply_attempt.case_snapshot)
    snapshot["rubric"]["criteria"] = [
        {"criterion": "Keeps key private", "skill_id": "secret_isolation"},
        {"criterion": "Revokes leaked credential", "skill_id": "credential_lifecycle"}
    ]
    apply_attempt.case_snapshot = snapshot

    # Row 1: Demonstrated
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="demonstrated",
            met=True,
            evidence="Key is stored on server only"
        )
    )
    # Row 2: Ambiguous (met=None)
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Revokes leaked credential",
            skill_id="credential_lifecycle",
            rating="ambiguous_needs_clarification",
            met=None,
            evidence="Unclear if revoked"
        )
    )
    db.commit()

    report = service.generate_report(session)
    unfam = report.session_summary["unfamiliar_case_summary"]
    # Must NOT claim all criteria were demonstrated
    assert "demonstrated all 2 criteria" not in unfam.lower()
    assert "demonstrated all" not in unfam.lower()
    assert "1 of 2" in unfam or "demonstrated 1" in unfam
    assert "ambiguous" in unfam.lower() or "clarification" in unfam.lower()
    assert report.outcome == "inconclusive"


@pytest.mark.asyncio
async def test_issue1_demonstrated_plus_missing(loop):
    """Two criteria in frozen rubric, but only one assessment row exists (other is missing)."""
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Transfer answer with missing row.")

    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    assert apply_attempt is not None, "Apply attempt must exist"
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    # Two prepared criteria in snapshot:
    snapshot = deepcopy(apply_attempt.case_snapshot)
    snapshot["rubric"]["criteria"] = [
        {"criterion": "Keeps key private", "skill_id": "secret_isolation"},
        {"criterion": "Revokes leaked credential", "skill_id": "credential_lifecycle"}
    ]
    apply_attempt.case_snapshot = snapshot

    # ONLY ONE row recorded (the second is missing)
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="demonstrated",
            met=True,
            evidence="Key is kept on server"
        )
    )
    db.commit()

    report = service.generate_report(session)
    unfam = report.session_summary["unfamiliar_case_summary"]
    # Must NOT claim "Demonstrated all 1 criteria independently" when 2 were expected
    assert "demonstrated all 1" not in unfam.lower()
    assert "demonstrated all" not in unfam.lower()
    assert "missing" in unfam.lower()
    assert "1 of 2" in unfam or "demonstrated 1" in unfam
    assert report.outcome == "inconclusive"


@pytest.mark.asyncio
async def test_issue1_demonstrated_plus_technical_failure(loop):
    """Demonstrated + technical failure must report unavailable failure and not claim full success."""
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Transfer answer with technical failure.")

    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    assert apply_attempt is not None, "Apply attempt must exist"
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    snapshot = deepcopy(apply_attempt.case_snapshot)
    snapshot["rubric"]["criteria"] = [
        {"criterion": "Keeps key private", "skill_id": "secret_isolation"},
        {"criterion": "Revokes leaked credential", "skill_id": "credential_lifecycle"}
    ]
    apply_attempt.case_snapshot = snapshot

    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="demonstrated",
            met=True,
            evidence="Key isolated"
        )
    )
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Revokes leaked credential",
            skill_id="credential_lifecycle",
            rating="technical_failure",
            met=None,
            evidence=None
        )
    )
    db.commit()

    report = service.generate_report(session)
    unfam = report.session_summary["unfamiliar_case_summary"]
    assert "demonstrated all" not in unfam.lower()
    assert "technical failure" in unfam.lower()
    assert "1 of 2" in unfam or "demonstrated 1" in unfam
    assert report.outcome == "inconclusive"


@pytest.mark.asyncio
async def test_issue1_demonstrated_plus_unmet_plus_ambiguous(loop):
    """Demonstrated + unmet + ambiguous handles mixed combinations cleanly."""
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Transfer answer with 3 criteria.")

    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    assert apply_attempt is not None, "Apply attempt must exist"
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    snapshot = deepcopy(apply_attempt.case_snapshot)
    snapshot["rubric"]["criteria"] = [
        {"criterion": "Keeps key private", "skill_id": "secret_isolation"},
        {"criterion": "Revokes leaked credential", "skill_id": "credential_lifecycle"},
        {"criterion": "Rotates secrets safely", "skill_id": "secret_rotation"}
    ]
    apply_attempt.case_snapshot = snapshot

    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="demonstrated",
            met=True
        )
    )
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Revokes leaked credential",
            skill_id="credential_lifecycle",
            rating="not_addressed",
            met=False
        )
    )
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Rotates secrets safely",
            skill_id="secret_rotation",
            rating="ambiguous_needs_clarification",
            met=None
        )
    )
    db.commit()

    report = service.generate_report(session)
    unfam = report.session_summary["unfamiliar_case_summary"]
    assert "demonstrated all" not in unfam.lower()
    assert "1 of 3" in unfam
    assert "unmet" in unfam.lower()
    assert "ambiguous" in unfam.lower() or "clarification" in unfam.lower()
    # Missing or ambiguous evidence must not become either success or learner failure -> inconclusive
    assert report.outcome == "inconclusive"


@pytest.mark.asyncio
async def test_issue1_fully_assessed_positive_control_case(loop):
    """Control case: all criteria demonstrated independently produces 'Demonstrated all N criteria independently'."""
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Full positive transfer answer.")

    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    assert apply_attempt is not None, "Apply attempt must exist"
    apply_attempt.support_level = "independent"
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    snapshot = deepcopy(apply_attempt.case_snapshot)
    snapshot["rubric"]["criteria"] = [
        {"criterion": "Keeps key private", "skill_id": "secret_isolation"},
        {"criterion": "Revokes leaked credential", "skill_id": "credential_lifecycle"}
    ]
    apply_attempt.case_snapshot = snapshot

    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="demonstrated",
            met=True
        )
    )
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Revokes leaked credential",
            skill_id="credential_lifecycle",
            rating="demonstrated",
            met=True
        )
    )
    db.commit()

    report = service.generate_report(session)
    unfam = report.session_summary["unfamiliar_case_summary"]
    assert "demonstrated all 2 criteria independently" in unfam.lower()


# ============================================================================
# ISSUE 2: Untested concerns are still classified as current gaps
# ============================================================================

@pytest.mark.asyncio
async def test_issue2_untested_baseline_concern_outcome_is_inconclusive_not_gap_found(loop):
    """When an earlier concern is not covered by the unfamiliar case, outcome must be inconclusive, NOT gap_found."""
    db, _, service, session, send, baseline, _, cases = loop
    # Ensure diagnostic case has multiple criteria in its rubric before baseline runs:
    cases[0].rubric.criteria = [
        {"criterion": "Explains memory lifetime", "skill_id": "memory_lifetime"},
        {"criterion": "Distinguishes saved records from screen state", "skill_id": "save_boundary"}
    ]
    db.commit()

    await baseline()

    # Strictly assert and find criteria
    crit_lifecycle = db.query(CriterionAssessment).join(Attempt).filter(
        Attempt.session_id == session.id,
        Attempt.stage == "diagnostic",
        CriterionAssessment.skill_id == "memory_lifetime"
    ).first()
    assert crit_lifecycle is not None, "Baseline memory_lifetime criterion must exist"
    crit_lifecycle.met = False
    crit_lifecycle.rating = "not_addressed"

    crit_boundary = db.query(CriterionAssessment).join(Attempt).filter(
        Attempt.session_id == session.id,
        Attempt.stage == "diagnostic",
        CriterionAssessment.skill_id == "save_boundary"
    ).first()
    assert crit_boundary is not None, "Baseline save_boundary criterion must exist"
    crit_boundary.met = True
    crit_boundary.rating = "demonstrated"
    db.commit()

    # Unfamiliar case tests ONLY save_boundary successfully; memory_lifetime was never rechecked
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Save boundary demonstrated independently.")
    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    assert apply_attempt is not None, "Apply attempt must exist"
    apply_attempt.support_level = "independent"
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
    snapshot = deepcopy(apply_attempt.case_snapshot)
    snapshot["rubric"]["criteria"] = [
        {"criterion": "Distinguishes saved records from screen state", "skill_id": "save_boundary"}
    ]
    apply_attempt.case_snapshot = snapshot
    db.commit()

    report = service.generate_report(session)
    # Outcome MUST be inconclusive, not gap_found (which shows 'CRITERIA NEEDING ATTENTION')
    assert report.outcome == "inconclusive", f"Expected inconclusive, got {report.outcome}"
    assert "save boundary" in report.outcome_reason.lower()
    assert "memory lifetime" in report.outcome_reason.lower()
    assert "not rechecked" in report.outcome_reason.lower()

    # Historical baseline ratings must remain preserved
    assert crit_lifecycle.met is False
    assert crit_lifecycle.rating == "not_addressed"

    # Unresolved summary treats untested concern as unresolved/uncertain
    assert any("memory lifetime" in item.lower() and "not rechecked" in item.lower()
               for item in report.session_summary["unresolved_summary"].split("; "))


# ============================================================================
# ISSUE 3: Independence changes wording but does not gate the positive outcome
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("support_level,expected_outcome,expected_desc", [
    ("independent", "criteria_demonstrated", "independently"),
    ("unknown", "inconclusive", "unknown"),
    ("legacy_unknown", "inconclusive", "unknown"),
    ("after_teaching", "inconclusive", "supported"),
    ("after_hint", "inconclusive", "supported"),
])
async def test_issue3_independence_gates_positive_outcome(loop, support_level, expected_outcome, expected_desc):
    """Unknown or supported transfer must leave independent confirmation inconclusive."""
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()

    # Baseline had a gap
    diag_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="diagnostic").first()
    assert diag_attempt is not None
    diag_crit = next(c for c in diag_attempt.criterion_assessments if c.skill_id == "memory_lifetime")
    diag_crit.met = False
    diag_crit.rating = "not_addressed"

    gap = Gap(
        session_id=session.id,
        source_attempt_id=diag_attempt.id,
        description="Needs clarification: Explains memory lifetime.",
        probe_text="Explain lifetime.",
        status="identified"
    )
    db.add(gap)
    db.commit()

    # Revision addresses it
    await send(action="submit_answer", text="Revised explanation.")
    rev_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="investigate").first()
    assert rev_attempt is not None
    rev_attempt.support_level = "after_hint"
    for ca in rev_attempt.criterion_assessments:
        ca.met = True
        ca.rating = "demonstrated"
    db.commit()

    # Transfer case demonstrates all criteria
    await send(action="submit_answer", text="Transfer answer.")
    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    assert apply_attempt is not None
    apply_attempt.support_level = support_level
    for ca in apply_attempt.criterion_assessments:
        ca.met = True
        ca.rating = "demonstrated"
    db.commit()

    report = service.generate_report(session)
    assert report.outcome == expected_outcome, f"For {support_level}, expected {expected_outcome} but got {report.outcome}"
    if support_level == "independent":
        assert report.final_score is not None
        assert "independently" in report.session_summary["unfamiliar_case_summary"].lower()
    else:
        assert report.final_score is None
        assert expected_desc in report.session_summary["unfamiliar_case_summary"].lower()


# ============================================================================
# ISSUE 4: Compound concerns can still be marked addressed after only one part succeeds
# ============================================================================

@pytest.mark.asyncio
async def test_issue4_compound_concern_only_one_part_succeeds_remains_unaddressed(loop):
    """Compound concern with 2 criteria: if only one part succeeds and the other is unmet, gap is NOT addressed."""
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()

    diag_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="diagnostic").first()
    assert diag_attempt is not None

    # Replace criteria on diagnostic attempt with two specific criteria
    for row in list(diag_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    diag_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=diag_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="not_addressed",
            met=False
        )
    )
    diag_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=diag_attempt.id,
            criterion="Revokes leaked credential",
            skill_id="credential_lifecycle",
            rating="not_addressed",
            met=False
        )
    )
    snapshot = deepcopy(diag_attempt.case_snapshot)
    snapshot["rubric"]["criteria"] = [
        {"criterion": "Keeps key private", "skill_id": "secret_isolation"},
        {"criterion": "Revokes leaked credential", "skill_id": "credential_lifecycle"}
    ]
    diag_attempt.case_snapshot = snapshot

    # Compound concern mentioning BOTH criteria
    gap = Gap(
        session_id=session.id,
        source_attempt_id=diag_attempt.id,
        description="Needs clarification: Keeps key private and Revokes leaked credential",
        probe_text="Explain isolation and revocation.",
        status="identified"
    )
    db.add(gap)
    db.commit()

    # Transfer case: Keeps key private is demonstrated, BUT Revokes leaked credential is unmet
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Transfer answer demonstrating only one part.")
    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    assert apply_attempt is not None
    apply_attempt.support_level = "independent"
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    apply_snapshot = deepcopy(apply_attempt.case_snapshot)
    apply_snapshot["rubric"]["criteria"] = [
        {"criterion": "Keeps key private", "skill_id": "secret_isolation"},
        {"criterion": "Revokes leaked credential", "skill_id": "credential_lifecycle"}
    ]
    apply_attempt.case_snapshot = apply_snapshot

    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="demonstrated",
            met=True,
            evidence="Key is isolated"
        )
    )
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Revokes leaked credential",
            skill_id="credential_lifecycle",
            rating="not_addressed",
            met=False
        )
    )
    db.commit()

    report = service.generate_report(session)
    gap_rep = next(g for g in report.gaps if g.id == gap.id)
    # The entire compound concern must NOT be marked addressed because the second part was unmet!
    assert gap_rep.addressed_by_attempt_id is None, "Compound concern should not be marked addressed when one part failed"
    assert gap_rep.addressed_stage is None


# ============================================================================
# REMOVAL OF GUESSED CONCERN RESOLUTION
# ============================================================================

@pytest.mark.asyncio
async def test_unmatched_free_text_concern_remains_unaddressed(loop):
    """Regression A: Unmatched AI concern about isolation must NOT be guessed to map to lifecycle.

    Reproduction:
    - Baseline: secret_isolation = demonstrated, secret_lifecycle = unmet.
    - Stored concern: “The learner believes minified browser bundles hide the provider secret from site visitors.”
    - Independent unfamiliar case: secret_isolation = unmet, secret_lifecycle = demonstrated.

    Without the unsafe fallback, the isolation concern remains unaddressed (addressed_by_attempt_id=None).
    """
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()

    diag_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="diagnostic").first()
    assert diag_attempt is not None
    for row in list(diag_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    snapshot = deepcopy(diag_attempt.case_snapshot)
    snapshot["rubric"]["criteria"] = [
        {"criterion": "Keeps key private", "skill_id": "secret_isolation"},
        {"criterion": "Revokes leaked credential", "skill_id": "secret_lifecycle"}
    ]
    diag_attempt.case_snapshot = snapshot

    # Baseline: secret_isolation = demonstrated, secret_lifecycle = unmet
    diag_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=diag_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="demonstrated",
            met=True,
            evidence="Key is held on the server"
        )
    )
    diag_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=diag_attempt.id,
            criterion="Revokes leaked credential",
            skill_id="secret_lifecycle",
            rating="not_addressed",
            met=False
        )
    )

    # Free-text AI concern with no keyword match to the unmet criterion
    concern_text = "The learner believes minified browser bundles hide the provider secret from site visitors."
    evidence_text = "Minification obscures the key."
    probe_text = "Why does client bundling expose secrets?"
    gap = Gap(
        session_id=session.id,
        source_attempt_id=diag_attempt.id,
        description=concern_text,
        evidence_quote=evidence_text,
        probe_text=probe_text,
        status="identified"
    )
    db.add(gap)
    db.commit()

    # Move to unfamiliar transfer case
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Transfer answer demonstrating lifecycle but failing isolation.")
    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    assert apply_attempt is not None
    apply_attempt.support_level = "independent"
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    apply_snapshot = deepcopy(apply_attempt.case_snapshot)
    apply_snapshot["rubric"]["criteria"] = [
        {"criterion": "Keeps key private", "skill_id": "secret_isolation"},
        {"criterion": "Revokes leaked credential", "skill_id": "secret_lifecycle"}
    ]
    apply_attempt.case_snapshot = apply_snapshot

    # Unfamiliar case: secret_isolation = unmet, secret_lifecycle = demonstrated
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="not_addressed",
            met=False
        )
    )
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Revokes leaked credential",
            skill_id="secret_lifecycle",
            rating="demonstrated",
            met=True,
            evidence="Key was revoked immediately"
        )
    )
    db.commit()

    report = service.generate_report(session)
    gap_rep = next(g for g in report.gaps if g.id == gap.id)

    # The isolation concern must NOT be guessed to map to lifecycle
    assert gap_rep.addressed_by_attempt_id is None, "Unmatched concern must remain unaddressed without guessing"
    assert gap_rep.addressed_stage is None

    # Verify historical records in DB remain completely unchanged
    stored_gap = db.query(Gap).filter_by(id=gap.id).first()
    assert stored_gap.description == concern_text
    assert stored_gap.evidence_quote == evidence_text
    assert stored_gap.probe_text == probe_text
    assert stored_gap.status == "identified"
    assert stored_gap.source_attempt_id == diag_attempt.id


@pytest.mark.asyncio
async def test_explicitly_mapped_concern_resolves_when_demonstrated(loop):
    """Regression B: Explicitly mapped concern still resolves when relevant later evidence demonstrates it."""
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()

    diag_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="diagnostic").first()
    assert diag_attempt is not None
    for row in list(diag_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    snapshot = deepcopy(diag_attempt.case_snapshot)
    snapshot["rubric"]["criteria"] = [
        {"criterion": "Keeps key private", "skill_id": "secret_isolation"},
        {"criterion": "Revokes leaked credential", "skill_id": "secret_lifecycle"}
    ]
    diag_attempt.case_snapshot = snapshot

    diag_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=diag_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="demonstrated",
            met=True
        )
    )
    diag_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=diag_attempt.id,
            criterion="Revokes leaked credential",
            skill_id="secret_lifecycle",
            rating="not_addressed",
            met=False
        )
    )

    # Stored concern explicitly mentions "Revokes leaked credential"
    gap = Gap(
        session_id=session.id,
        source_attempt_id=diag_attempt.id,
        description="Needs clarification: Revokes leaked credential after accidental exposure.",
        evidence_quote="No rotation or revocation procedure mentioned.",
        status="identified"
    )
    db.add(gap)
    db.commit()

    # Move to unfamiliar transfer case
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Transfer answer successfully revoking credential.")
    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    assert apply_attempt is not None
    apply_attempt.support_level = "independent"
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    apply_snapshot = deepcopy(apply_attempt.case_snapshot)
    apply_snapshot["rubric"]["criteria"] = [
        {"criterion": "Keeps key private", "skill_id": "secret_isolation"},
        {"criterion": "Revokes leaked credential", "skill_id": "secret_lifecycle"}
    ]
    apply_attempt.case_snapshot = apply_snapshot

    # Both criteria demonstrated in independent unfamiliar case
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="demonstrated",
            met=True
        )
    )
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Revokes leaked credential",
            skill_id="secret_lifecycle",
            rating="demonstrated",
            met=True,
            evidence="Rotated and revoked in provider console"
        )
    )
    db.commit()

    report = service.generate_report(session)
    gap_rep = next(g for g in report.gaps if g.id == gap.id)

    # Explicitly mapped concern resolves to the transfer attempt
    assert gap_rep.addressed_by_attempt_id == apply_attempt.id
    assert gap_rep.addressed_stage == "Unfamiliar case (independent)"

    # Verify historical records in DB remain unchanged
    stored_gap = db.query(Gap).filter_by(id=gap.id).first()
    assert stored_gap.description == "Needs clarification: Revokes leaked credential after accidental exposure."
    assert stored_gap.source_attempt_id == diag_attempt.id


@pytest.mark.asyncio
async def test_compound_concern_remains_unaddressed_until_every_target_demonstrated(loop):
    """Regression C: Compound concern remains unaddressed until every relevant target is demonstrated."""
    db, _, service, session, send, baseline, _, _ = loop
    await baseline()

    diag_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="diagnostic").first()
    assert diag_attempt is not None
    for row in list(diag_attempt.criterion_assessments):
        db.delete(row)
    db.commit()

    snapshot = deepcopy(diag_attempt.case_snapshot)
    snapshot["rubric"]["criteria"] = [
        {"criterion": "Keeps key private", "skill_id": "secret_isolation"},
        {"criterion": "Revokes leaked credential", "skill_id": "secret_lifecycle"}
    ]
    diag_attempt.case_snapshot = snapshot

    diag_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=diag_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="not_addressed",
            met=False
        )
    )
    diag_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=diag_attempt.id,
            criterion="Revokes leaked credential",
            skill_id="secret_lifecycle",
            rating="not_addressed",
            met=False
        )
    )

    # Compound concern explicitly referencing BOTH criteria
    gap = Gap(
        session_id=session.id,
        source_attempt_id=diag_attempt.id,
        description="Needs clarification: Keeps key private and Revokes leaked credential.",
        evidence_quote="No private key isolation and no revocation.",
        status="identified"
    )
    db.add(gap)
    db.commit()

    # Move to unfamiliar case
    await send(action="continue", text=None)
    await send(action="submit_answer", text="Transfer answer.")
    apply_attempt = db.query(Attempt).filter_by(session_id=session.id, stage="apply").first()
    assert apply_attempt is not None
    apply_attempt.support_level = "independent"

    apply_snapshot = deepcopy(apply_attempt.case_snapshot)
    apply_snapshot["rubric"]["criteria"] = [
        {"criterion": "Keeps key private", "skill_id": "secret_isolation"},
        {"criterion": "Revokes leaked credential", "skill_id": "secret_lifecycle"}
    ]
    apply_attempt.case_snapshot = apply_snapshot

    # Scenario 1: Only ONE of the two criteria is demonstrated (partial)
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="demonstrated",
            met=True,
            evidence="Key is stored on backend"
        )
    )
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Revokes leaked credential",
            skill_id="secret_lifecycle",
            rating="not_addressed",
            met=False
        )
    )
    db.commit()

    report_partial = service.generate_report(session)
    gap_partial = next(g for g in report_partial.gaps if g.id == gap.id)
    assert gap_partial.addressed_by_attempt_id is None, "Compound concern must NOT resolve when only one part is demonstrated"
    assert gap_partial.addressed_stage is None

    # Scenario 2: BOTH criteria are demonstrated
    for row in list(apply_attempt.criterion_assessments):
        db.delete(row)
    db.commit()
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Keeps key private",
            skill_id="secret_isolation",
            rating="demonstrated",
            met=True,
            evidence="Key is stored on backend"
        )
    )
    apply_attempt.criterion_assessments.append(
        CriterionAssessment(
            attempt_id=apply_attempt.id,
            criterion="Revokes leaked credential",
            skill_id="secret_lifecycle",
            rating="demonstrated",
            met=True,
            evidence="Rotated and revoked"
        )
    )
    db.commit()

    report_complete = service.generate_report(session)
    gap_complete = next(g for g in report_complete.gaps if g.id == gap.id)
    assert gap_complete.addressed_by_attempt_id == apply_attempt.id, "Compound concern must resolve when ALL targets are demonstrated"
    assert gap_complete.addressed_stage == "Unfamiliar case (independent)"

    # Verify historical records in DB remain unchanged
    stored_gap = db.query(Gap).filter_by(id=gap.id).first()
    assert stored_gap.description == "Needs clarification: Keeps key private and Revokes leaked credential."
    assert stored_gap.source_attempt_id == diag_attempt.id

