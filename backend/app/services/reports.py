"""Assemble reports from stored evidence, without asking a model to invent progress."""
from sqlalchemy import desc
from app.db.models import Attempt, CasePrompt, Concept, CriterionAssessment, Gap, Intervention, Session
from app.schemas import AttemptReport, GapReport, SessionReport
from app.services.evidence import snapshot_case


def attempt_reports(db, session):
    reports = []
    for attempt in db.query(Attempt).filter_by(session_id=session.id).order_by(Attempt.created_at, Attempt.id):
        case = db.get(CasePrompt, attempt.case_prompt_id)
        has_snapshot = bool(attempt.case_snapshot)
        snapshot = attempt.case_snapshot or (snapshot_case(case) if case else {})
        criteria = [{"criterion": c.criterion, "skill_id": c.skill_id, "rating": c.rating,
            "met": c.met, "evidence": c.evidence, "status": c.status, "reviewer_notes": c.reviewer_notes}
            for c in attempt.criterion_assessments]
        crit_list = [c for c in criteria if not (c.get("skill_id") or "").startswith("exercise:")]
        expected = {c["criterion"] for c in snapshot.get("rubric", {}).get("criteria", [])}
        actual = {c["criterion"] for c in crit_list}
        total_count = len(expected) if has_snapshot else len(crit_list)
        met_count = sum(c.get("met") is True and c.get("rating") == "demonstrated" for c in crit_list)
        missing_count = len(expected - actual)
        unavailable_count = missing_count + sum(c.get("rating") == "technical_failure" for c in crit_list)
        uncertain_count = sum(c.get("rating") != "technical_failure" and c.get("met") is None for c in crit_list)
        usable = (has_snapshot and bool(expected) and expected == actual and len(crit_list) == len(expected)
            and attempt.processing_status == "complete" and not unavailable_count and not uncertain_count
            and all((c.get("rating"), c.get("met")) in {
                ("demonstrated", True), ("partially_demonstrated", False), ("not_addressed", False)} for c in crit_list))
        attempt_score = round(met_count / total_count * 100) if usable else None
        reports.append(AttemptReport(id=attempt.id, case_prompt_id=attempt.case_prompt_id,
            case_version=snapshot.get("version") if has_snapshot else None, rubric_version=attempt.rubric_version,
            provenance_warning=None if has_snapshot else "This legacy attempt has no frozen case snapshot. The displayed case is the current reference; its original wording and support history cannot be established.",
            stage=attempt.stage, case_type=snapshot.get("case_type", "unknown"),
            scenario_text=snapshot.get("scenario_text", ""), answer_text=attempt.answer_text,
            response_format=snapshot.get("response_format", "written"),
            diagram_preset=snapshot.get("diagram_preset"), cloze_preset=snapshot.get("cloze_preset"),
            diagram_state=attempt.diagram_state, cloze_state=attempt.cloze_state, criteria=criteria,
            support_level=(attempt.support_level or "unknown") if has_snapshot else "unknown",
            processing_status=attempt.processing_status or "complete", created_at=attempt.created_at,
            gap_id=attempt.gap_id, score=attempt_score, met_criteria_count=met_count, total_criteria_count=total_count,
            uncertain_criteria_count=uncertain_count, unavailable_criteria_count=unavailable_count))
    return reports


def skill_comparisons(reports):
    skills = {}
    for attempt in reports:
        bucket = {"diagnostic": "baseline", "investigate": "revision", "apply": "transfer"}.get(attempt.stage)
        if not bucket:
            continue
        for criterion in attempt.criteria:
            skill = criterion.get("skill_id") or criterion["criterion"]
            if skill.startswith("exercise:"):
                continue
            item = skills.setdefault(skill, {"skill_id": skill, "label": skill.replace("_", " ").capitalize(),
                "baseline": [], "revision": [], "transfer": [], "change_summary": "", "review_status": "provisional"})
            item[bucket].append({"attempt_id": attempt.id, "case_type": attempt.case_type,
                "support_level": attempt.support_level, **criterion})
    for item in skills.values():
        before, after = item["baseline"], item["transfer"]
        all_rows = before + item["revision"] + after
        item["review_status"] = "reviewed" if all_rows and all(c["status"] in ("reviewed", "corrected") for c in all_rows) else "provisional"
        if not before or not after:
            text = "A matched initial answer and unfamiliar-case answer are both needed for comparison."
        elif any(c.get("met") is None or c.get("rating") == "technical_failure" for c in before + after):
            text = "Some evidence is uncertain or assessment was unavailable; no reliable change judgment can be made."
        elif all(c.get("met") is True for c in after):
            text = ("The initial and unfamiliar-case answers met the prepared criteria for this skill."
                if all(c.get("met") is True for c in before) else
                "The later unfamiliar-case answer met the criteria where the initial evidence was incomplete or did not. This describes observed reasoning, not proof that tutoring caused learning.")
        else:
            text = "Some criteria remain unmet on the unfamiliar case; inspect the quoted evidence and any missing reasoning."
        if item["review_status"] != "reviewed":
            text += " Model judgments remain provisional until human review."
        item["change_summary"] = text
    return list(skills.values())


def stage_summaries(reports, baseline_complete):
    """Describe separate attempted cases; never turn raw totals into learning gain."""
    result = []
    for stage, source in (("baseline", "diagnostic"), ("revision", "investigate"), ("transfer", "apply")):
        attempts = [a for a in reports if a.stage == source]
        met = sum(a.met_criteria_count or 0 for a in attempts)
        total = sum(a.total_criteria_count or 0 for a in attempts)
        assessed = bool(attempts) and all(a.score is not None for a in attempts)
        if stage == "baseline":
            assessed = assessed and baseline_complete
        result.append({"stage": stage, "attempt_count": len(attempts), "met_count": met, "total_count": total,
            "uncertain_count": sum(a.uncertain_criteria_count for a in attempts),
            "unavailable_count": sum(a.unavailable_criteria_count for a in attempts),
            "percentage": round(met / total * 100) if assessed and total else None,
            "status": "not_assessed" if not attempts else "assessed" if assessed else "partial",
            "support_levels": sorted({a.support_level for a in attempts})})
    return result


def build_report(db, session, include_history=True):
    reports = attempt_reports(db, session)
    attempts = db.query(Attempt).filter_by(session_id=session.id).all()
    conceptual = [c for a in reports if a.stage != "practice" for c in a.criteria
        if not (c.get("skill_id") or "").startswith("exercise:")]
    all_rows = [c for a in reports if a.stage != "practice" for c in a.criteria]
    expected_ids = session.baseline_prompt_ids or [c.id for c in db.query(CasePrompt).filter_by(
        concept_id=session.concept_id, stage="diagnostic", active=True).all()]
    baseline_done = {a.case_prompt_id for a in attempts if a.stage == "diagnostic"}
    full_criteria = True
    for attempt in attempts:
        if attempt.stage == "practice":
            continue
        snapshot = attempt.case_snapshot or (snapshot_case(attempt.case_prompt) if attempt.case_prompt else {})
        expected = {c["criterion"] for c in snapshot.get("rubric", {}).get("criteria", [])}
        actual = {c.criterion for c in attempt.criterion_assessments if not (c.skill_id or "").startswith("exercise:")}
        full_criteria = full_criteria and bool(attempt.case_snapshot) and bool(expected) and expected == actual and attempt.processing_status == "complete"
    reviewed = bool(all_rows) and full_criteria and all(c["status"] in ("reviewed", "corrected") for c in all_rows)
    complete = (session.stage in ("review", "completed") and bool(expected_ids) and set(expected_ids) == baseline_done
        and any(a.stage == "apply" for a in attempts) and full_criteria and bool(conceptual)
        and (session.baseline_analysis_status == "complete" or reviewed)
        and all(c["met"] is not None and c.get("rating") != "technical_failure" for c in all_rows))
    gaps = db.query(Gap).filter_by(session_id=session.id).order_by(Gap.created_at).all()
    if not complete:
        outcome, reason = "inconclusive", "The session is partial or some prepared criteria lack usable assessment evidence. Saved answers remain available for review."
    elif any(c["met"] is False for c in all_rows):
        outcome, reason = "gap_found", "Some tested criteria were not met. Inspect the per-skill comparison to distinguish initial difficulties from unresolved unfamiliar-case reasoning. An omission or incorrect selection alone is not a confirmed misconception."
    elif gaps and not reviewed:
        outcome, reason = "inconclusive", "A possible gap was proposed but all criterion judgments were positive. Human review must resolve this disagreement."
    else:
        outcome, reason = "no_gap", "The prepared criteria were met in the cases tested. This does not establish complete mastery or retained learning."
    interventions = db.query(Intervention).filter_by(session_id=session.id).order_by(Intervention.created_at).all()
    concept = db.get(Concept, session.concept_id)
    previous = []
    if include_history:
        rows = db.query(Session).filter(Session.owner_id == session.owner_id, Session.concept_id == session.concept_id,
            Session.id != session.id, Session.created_at < session.created_at,
            Session.stage.in_(["completed", "review"])).order_by(desc(Session.created_at)).limit(5).all()
        for earlier in rows:
            other = build_report(db, earlier, include_history=False)
            previous.append({"session_id": earlier.id, "created_at": earlier.created_at.isoformat(),
                "outcome": other.outcome, "skill_comparisons": other.skill_comparisons})

    summaries = stage_summaries(reports, bool(expected_ids) and set(expected_ids) == baseline_done)
    initial_score = summaries[0]["percentage"]
    final_score = summaries[2]["percentage"] if summaries[2]["support_levels"] == ["independent"] else None
    # Compatibility fields describe criteria in these cases, never mastery or
    # a before/after difference across differently scoped questions.
    score_summary = "; ".join(f"{s['stage'].capitalize()}: " + (
        "not assessed" if s["status"] == "not_assessed" else
        f"{s['met_count']}/{s['total_count']} criteria demonstrated" + ("; assessment incomplete" if s["status"] == "partial" else ""))
        for s in summaries)

    return SessionReport(session_id=session.id, concept_title=concept.title if concept else "", stage=session.stage,
        outcome=outcome, outcome_reason=reason, assessment_status="reviewed" if reviewed else "provisional",
        gaps=[GapReport(id=g.id, description=g.description, evidence_quote=g.evidence_quote,
            probe_text=g.probe_text, status=g.status, source_attempt_id=g.source_attempt_id) for g in gaps],
        attempts=reports, interventions_used=[{"id": i.id, "type": i.intervention_type, "title": i.title,
            "status": i.status, "url": i.url, "content": i.content, "opened": i.opened_at is not None, "completed": i.completed_at is not None,
            "created_at": i.created_at.isoformat()} for i in interventions], skill_comparisons=skill_comparisons(reports),
        previous_sessions=previous, processing_status=session.processing_status or "idle",
        initial_score=initial_score, final_score=final_score, score_change=None, score_summary=score_summary,
        stage_summaries=summaries)

