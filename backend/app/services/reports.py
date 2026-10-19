"""Assemble reports from stored evidence, without asking a model to invent progress."""
from sqlalchemy import desc
from app.db.models import Attempt, CasePrompt, Concept, CriterionAssessment, Gap, Intervention, Session
from app.schemas import AttemptReport, GapReport, SessionReport
from app.services.evidence import snapshot_case


def check_unprompted(criterion_name, skill_id, scenario_text, assumptions, rubric_criterion=None):
    if rubric_criterion and isinstance(rubric_criterion, dict):
        if rubric_criterion.get("unprompted") is True or rubric_criterion.get("applicability") == "unprompted":
            note = rubric_criterion.get("unprompted_note") or "The scenario did not explicitly ask how to handle this requirement."
            return True, note
        if rubric_criterion.get("unprompted") is False or rubric_criterion.get("applicability") == "explicit":
            return False, None
        if rubric_criterion.get("applicability") in ("uncertain", "review_needed"):
            return False, "Criterion applicability to the scenario prompt is uncertain and requires review."

    full_prompt = f"{scenario_text} {' '.join(assumptions or [])}".lower()
    if skill_id == "secret_lifecycle":
        keywords = [
            "replace", "rotat", "revok", "download", "earlier cop", "lifecycle",
            "what to do about", "copies", "handle the shipped credential",
            "incident response", "earlier exposure", "shipped that value", "remaining action"
        ]
        if any(k in full_prompt for k in keywords):
            return False, None
        return False, None
    return False, None


def attempt_reports(db, session):
    reports = []
    for attempt in db.query(Attempt).filter_by(session_id=session.id).order_by(Attempt.created_at, Attempt.id):
        case = db.get(CasePrompt, attempt.case_prompt_id)
        has_snapshot = bool(attempt.case_snapshot)
        snapshot = attempt.case_snapshot or (snapshot_case(case) if case else {})
        criteria = []
        rubric_criteria = snapshot.get("rubric", {}).get("criteria", [])
        for c in attempt.criterion_assessments:
            rubric_crit = next((rc for rc in rubric_criteria if rc.get("criterion") == c.criterion or rc.get("skill_id") == c.skill_id), None)
            is_unprompted, unprompted_note = check_unprompted(c.criterion, c.skill_id, snapshot.get("scenario_text", ""), snapshot.get("assumptions") or [], rubric_crit)
            criteria.append({
                "criterion": c.criterion, "skill_id": c.skill_id, "rating": c.rating,
                "met": c.met, "evidence": c.evidence, "status": c.status, "reviewer_notes": c.reviewer_notes,
                "unprompted": is_unprompted, "unprompted_note": unprompted_note,
            })
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

    transfer_attempts = [a for a in reports if a.stage == "apply"]
    transfer_criteria = [c for a in transfer_attempts for c in a.criteria if not (c.get("skill_id") or "").startswith("exercise:")]
    revision_attempts = [a for a in reports if a.stage == "investigate"]
    revision_criteria = [c for a in revision_attempts for c in a.criteria if not (c.get("skill_id") or "").startswith("exercise:")]
    baseline_attempts = [a for a in reports if a.stage == "diagnostic"]
    baseline_criteria = [c for a in baseline_attempts for c in a.criteria if not (c.get("skill_id") or "").startswith("exercise:")]

    # Derive expected transfer criteria from frozen rubrics
    expected_transfer_criteria = []
    for a in attempts:
        if a.stage == "apply":
            snapshot = a.case_snapshot or (snapshot_case(a.case_prompt) if a.case_prompt else {})
            for rc in snapshot.get("rubric", {}).get("criteria", []):
                if not (rc.get("skill_id") or "").startswith("exercise:"):
                    expected_transfer_criteria.append(rc)
    actual_transfer_crit_names = {c.get("criterion") for c in transfer_criteria}
    transfer_missing = [rc for rc in expected_transfer_criteria if rc.get("criterion") not in actual_transfer_crit_names]
    expected_transfer_count = len(expected_transfer_criteria) if expected_transfer_criteria else len(transfer_criteria)

    # Categorize transfer criteria semantics
    transfer_demonstrated = [c for c in transfer_criteria if c.get("met") is True and c.get("rating") == "demonstrated"]
    transfer_unmet = [c for c in transfer_criteria if c.get("met") is False]
    transfer_ambiguous = [c for c in transfer_criteria if c.get("met") is None and c.get("rating") != "technical_failure"]
    transfer_technical_failures = [c for c in transfer_criteria if c.get("rating") == "technical_failure"]

    transfer_support_levels = {a.support_level for a in transfer_attempts}
    transfer_is_independent = bool(transfer_attempts) and transfer_support_levels == {"independent"}
    unknown_support_values = {"unknown", "legacy_unknown"}
    transfer_support_unknown = bool(transfer_attempts) and any(a.support_level in unknown_support_values for a in transfer_attempts)
    support_used_labels = sorted({a.support_level for a in transfer_attempts if a.support_level not in ({"independent"} | unknown_support_values)})
    support_used_str = ", ".join(s.replace("_", " ") for s in support_used_labels) if support_used_labels else "supported assistance"

    # Categorize baseline criteria semantics
    baseline_unmet = [c for c in baseline_criteria if c.get("met") is False]
    baseline_concern_criteria = [c for c in baseline_criteria if c.get("met") is not True or c.get("rating") != "demonstrated"]
    baseline_skills = {c.get("skill_id") for c in baseline_criteria if c.get("skill_id")}
    baseline_concern_skills = {c.get("skill_id") for c in baseline_concern_criteria if c.get("skill_id")}

    revision_met = [c for c in revision_criteria if c.get("met") is True and c.get("rating") == "demonstrated"]
    revision_skills_met = {c.get("skill_id") for c in revision_met if c.get("skill_id")}

    transfer_skills_all = {c.get("skill_id") for c in transfer_criteria if c.get("skill_id")}
    concern_skills_not_rechecked = baseline_concern_skills - transfer_skills_all
    skills_not_rechecked = baseline_skills - transfer_skills_all

    all_conceptual_rows = [c for a in reports if a.stage != "practice" for c in a.criteria if not (c.get("skill_id") or "").startswith("exercise:")]
    all_positive = bool(all_conceptual_rows) and all(c.get("met") is True for c in all_conceptual_rows)

    num_map = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
    count_word = num_map.get(len(transfer_demonstrated), str(len(transfer_demonstrated)))
    support_desc = (
        "independently" if transfer_is_independent
        else "with unknown support provenance" if transfer_support_unknown
        else f"with supported assistance ({support_used_str})"
    )

    if not complete:
        outcome, reason = "inconclusive", "The session is partial or some prepared criteria lack usable assessment evidence. Saved answers remain available for review."
    elif transfer_unmet:
        outcome, reason = "gap_found", "Some tested criteria were not met on the unfamiliar case. Inspect the per-skill comparison to distinguish initial difficulties from unresolved unfamiliar-case reasoning. An omission or incorrect selection alone is not a confirmed misconception."
    elif concern_skills_not_rechecked:
        outcome = "inconclusive"
        tested_labels = [s.replace("_", " ").capitalize() for s in sorted(transfer_skills_all)]
        unrechecked_labels = [s.replace("_", " ").capitalize() for s in sorted(concern_skills_not_rechecked)]
        reason = f"Your unfamiliar-case answer demonstrated all {count_word} prepared criteria {support_desc} for {', '.join(tested_labels)}."
        reason += f" However, earlier difficulty with {', '.join(unrechecked_labels)} was not rechecked on the unfamiliar case and remains unassessed."
        if any(s in revision_skills_met for s in concern_skills_not_rechecked):
            reason += " A supported revision cannot substitute for independent unfamiliar-case evidence."
        reason += " Independent confirmation remains inconclusive because relevant criteria were not retested."
        reason += " AI assessments remain provisional." if not reviewed else " Human reviewed assessment."
    elif all_positive and gaps and not reviewed:
        outcome, reason = "inconclusive", "A possible gap was proposed but all criterion judgments were positive. Human review must resolve this disagreement."
    elif all_positive:
        if transfer_is_independent:
            outcome, reason = "no_gap", "The prepared criteria were met in the cases tested. This does not establish complete mastery or retained learning."
        elif transfer_support_unknown:
            outcome = "inconclusive"
            reason = "The prepared criteria were met in the cases tested, but transfer support provenance is unknown. Independent confirmation requires established independent support provenance."
        else:
            outcome = "inconclusive"
            reason = f"The prepared criteria were met in the cases tested with supported assistance ({support_used_str}). Independent transfer without coaching was not established; confirmation remains inconclusive."
    else:
        # All tested transfer criteria demonstrated, and all baseline concerns rechecked
        if transfer_is_independent:
            outcome = "criteria_demonstrated"
            reason = f"Your unfamiliar-case answer demonstrated all {count_word} prepared criteria independently."
        elif transfer_support_unknown:
            outcome = "inconclusive"
            reason = f"Your unfamiliar-case answer demonstrated all {count_word} prepared criteria, but support provenance is unknown. Independent confirmation requires established independent support provenance."
        else:
            outcome = "inconclusive"
            reason = f"Your unfamiliar-case answer demonstrated all {count_word} prepared criteria with supported assistance ({support_used_str}). Demonstrating criteria with support does not establish independent transfer; confirmation remains inconclusive."

        if revision_met:
            addressed_topics = []
            for c in revision_met:
                skill = c.get("skill_id") or c["criterion"]
                label = "exposed keys" if "secret" in skill or "key" in skill else skill.replace("_", " ")
                if label not in addressed_topics:
                    addressed_topics.append(label)
            topic_str = " and ".join(addressed_topics) if addressed_topics else "the earlier topics"
            reason += f" Your revised answer also addressed the earlier uncertainty about {topic_str}."
        reason += " AI assessments remain provisional." if not reviewed else " Human reviewed assessment."

    gaps_out = []
    for g in gaps:
        addressed_id = None
        addressed_stage = None
        source_a = next((a for a in reports if a.id == g.source_attempt_id), None)
        targets = []
        if source_a:
            g_desc = (g.description or "").lower()
            for c in source_a.criteria:
                c_name = (c.get("criterion") or "").lower()
                s_id = (c.get("skill_id") or "").lower()
                if (c_name and c_name in g_desc) or (s_id and (s_id in g_desc or s_id.replace("_", " ") in g_desc)):
                    targets.append(c)

        if targets:
            all_resolved = True
            any_transfer_failure = False
            all_transfer_demonstrated = True
            transfer_resolved_attempt = None
            revision_resolved_attempt = None

            for t in targets:
                t_crit = t.get("criterion")
                t_skill = t.get("skill_id")

                t_transfer_demonstrated = False
                for a in transfer_attempts:
                    for c in a.criteria:
                        matches = (t_skill and c.get("skill_id") == t_skill) or (t_crit and c.get("criterion") == t_crit)
                        if matches:
                            if c.get("met") is False or c.get("rating") in ("partially_demonstrated", "not_addressed"):
                                any_transfer_failure = True
                            elif c.get("met") is True and c.get("rating") == "demonstrated":
                                t_transfer_demonstrated = True
                                transfer_resolved_attempt = a

                t_revision_demonstrated = False
                for a in revision_attempts:
                    if a.id != g.source_attempt_id:
                        for c in a.criteria:
                            matches = (t_skill and c.get("skill_id") == t_skill) or (t_crit and c.get("criterion") == t_crit)
                            if matches and c.get("met") is True and c.get("rating") == "demonstrated":
                                t_revision_demonstrated = True
                                revision_resolved_attempt = a

                if not t_transfer_demonstrated:
                    all_transfer_demonstrated = False

                if not (t_transfer_demonstrated or t_revision_demonstrated):
                    all_resolved = False

            if any_transfer_failure:
                addressed_id = None
                addressed_stage = None
            elif all_resolved:
                if all_transfer_demonstrated and transfer_resolved_attempt:
                    addressed_id = transfer_resolved_attempt.id
                    if transfer_resolved_attempt.support_level == "independent":
                        addressed_stage = "Unfamiliar case (independent)"
                    elif transfer_resolved_attempt.support_level in ("unknown", "legacy_unknown"):
                        addressed_stage = "Unfamiliar case (support unknown)"
                    else:
                        addressed_stage = "Unfamiliar case (supported)"
                elif revision_resolved_attempt:
                    addressed_id = revision_resolved_attempt.id
                    addressed_stage = "Revised explanation (supported)"

        gaps_out.append(GapReport(id=g.id, description=g.description, evidence_quote=g.evidence_quote,
            probe_text=g.probe_text, status=g.status, source_attempt_id=g.source_attempt_id,
            addressed_by_attempt_id=addressed_id, addressed_stage=addressed_stage))

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
    score_summary = "; ".join(f"{s['stage'].capitalize()}: " + (
        "not assessed" if s["status"] == "not_assessed" else
        f"{s['met_count']}/{s['total_count']} criteria demonstrated" + ("; assessment incomplete" if s["status"] == "partial" else ""))
        for s in summaries)

    # Detailed session summary for report order A
    if not transfer_attempts:
        unfamiliar_summary = "Unfamiliar case was not attempted; independent transfer reasoning was not assessed."
    elif expected_transfer_count == 0 or (not transfer_criteria and not transfer_missing):
        unfamiliar_summary = "Unfamiliar-case answer was saved, but assessment is missing or unavailable; transfer reasoning was not assessed."
    elif len(transfer_technical_failures) == expected_transfer_count:
        unfamiliar_summary = f"Assessment was unavailable due to technical failure for all {len(transfer_technical_failures)} criteria; reassessment is available."
    elif len(transfer_missing) == expected_transfer_count:
        unfamiliar_summary = f"Assessment was missing or unavailable for all {len(transfer_missing)} prepared criteria; transfer reasoning was not assessed."
    elif len(transfer_ambiguous) == expected_transfer_count:
        unfamiliar_summary = f"Unfamiliar-case reasoning was ambiguous and requires clarification for all {len(transfer_ambiguous)} criteria."
    elif len(transfer_demonstrated) == expected_transfer_count and expected_transfer_count > 0 and not transfer_ambiguous and not transfer_unmet and not transfer_technical_failures and not transfer_missing:
        unfamiliar_skills = [c.get("skill_id") or c["criterion"] for c in transfer_criteria]
        labels = [s.replace("_", " ").capitalize() for s in unfamiliar_skills]
        if transfer_is_independent:
            unfamiliar_summary = f"Demonstrated all {expected_transfer_count} criteria independently on the unfamiliar case: {', '.join(labels)}."
        elif transfer_support_unknown:
            unfamiliar_summary = f"Demonstrated all {expected_transfer_count} criteria on the unfamiliar case (support provenance unknown): {', '.join(labels)}."
        else:
            unfamiliar_summary = f"Demonstrated all {expected_transfer_count} criteria on the unfamiliar case with supported assistance ({support_used_str}): {', '.join(labels)}."
    else:
        parts = [f"Unfamiliar-case answer demonstrated {len(transfer_demonstrated)} of {expected_transfer_count} prepared criteria."]
        if transfer_unmet:
            unmet_labels = [c.get("criterion") for c in transfer_unmet]
            parts.append(f"Remaining unmet: {', '.join(unmet_labels)}.")
        if transfer_ambiguous:
            amb_labels = [c.get("criterion") for c in transfer_ambiguous]
            parts.append(f"{len(transfer_ambiguous)} criterion/criteria ambiguous and require clarification ({', '.join(amb_labels)}).")
        if transfer_technical_failures:
            parts.append(f"{len(transfer_technical_failures)} criterion assessment(s) unavailable due to technical failure; reassessment is available.")
        if transfer_missing:
            missing_labels = [rc.get("criterion") for rc in transfer_missing]
            parts.append(f"Assessment was missing for {len(transfer_missing)} criterion/criteria ({', '.join(missing_labels)}).")
        unfamiliar_summary = " ".join(parts)

    if not revision_attempts:
        revised_summary = "No answer revision was submitted."
    else:
        rev_count = sum(a.met_criteria_count or 0 for a in revision_attempts)
        rev_total = sum(a.total_criteria_count or 0 for a in revision_attempts)
        support_used_labels_rev = sorted({a.support_level for a in revision_attempts})
        revised_summary = f"Revised answer demonstrated {rev_count} of {rev_total} criteria ({', '.join(support_used_labels_rev).replace('_', ' ')})."

    unresolved_items = []
    if transfer_unmet:
        unresolved_items.append(f"{len(transfer_unmet)} criterion/criteria unmet on unfamiliar case")
    if transfer_technical_failures:
        unresolved_items.append(f"{len(transfer_technical_failures)} criterion assessment(s) unavailable due to technical failure")
    if transfer_ambiguous:
        unresolved_items.append(f"{len(transfer_ambiguous)} criterion/criteria ambiguous and require clarification")
    if transfer_missing:
        unresolved_items.append(f"{len(transfer_missing)} criterion assessment(s) missing from unfamiliar case")

    for b_skill in sorted(baseline_skills):
        if b_skill not in transfer_skills_all:
            label = b_skill.replace("_", " ").capitalize()
            if b_skill in baseline_concern_skills:
                unresolved_items.append(f"Earlier concern with '{label}' was not rechecked on unfamiliar case")
            else:
                unresolved_items.append(f"Skill '{label}' not rechecked on unfamiliar case")

    if not complete:
        unresolved_items.append("Session is partial; remaining stages unassessed")
    unresolved_summary = "; ".join(unresolved_items) if unresolved_items else "None on tested cases. All tested criteria demonstrated; assessments remain provisional."

    support_counts = {}
    for i in interventions:
        kind = i.intervention_type.replace("_", " ").capitalize()
        support_counts[kind] = support_counts.get(kind, 0) + 1
    support_summary = ", ".join(f"{cnt} {k.lower()}" for k, cnt in support_counts.items()) if support_counts else "No external support recorded."

    session_summary = {
        "unfamiliar_case_summary": unfamiliar_summary,
        "revised_reasoning_summary": revised_summary,
        "unresolved_summary": unresolved_summary,
        "support_summary": support_summary,
    }

    return SessionReport(session_id=session.id, concept_title=concept.title if concept else "", stage=session.stage,
        outcome=outcome, outcome_reason=reason, assessment_status="reviewed" if reviewed else "provisional",
        gaps=gaps_out,
        attempts=reports, interventions_used=[{"id": i.id, "type": i.intervention_type, "title": i.title,
            "status": i.status, "url": i.url, "content": i.content, "opened": i.opened_at is not None, "completed": i.completed_at is not None,
            "created_at": i.created_at.isoformat()} for i in interventions], skill_comparisons=skill_comparisons(reports),
        previous_sessions=previous, processing_status=session.processing_status or "idle",
        initial_score=initial_score, final_score=final_score, score_change=None, score_summary=score_summary,
        stage_summaries=summaries, session_summary=session_summary)

