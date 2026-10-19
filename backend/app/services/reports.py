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
                "question_part_id": getattr(c, "question_part_id", None),
                "coverage": getattr(c, "coverage", None),
                "issue_type": getattr(c, "issue_type", None),
                "demonstrated_explanation": getattr(c, "demonstrated_explanation", None),
                "explanation": getattr(c, "explanation", None),
                "next_action": getattr(c, "next_action", None),
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
            question_parts=snapshot.get("question_parts"),
            question_parts_coverage=getattr(attempt, "question_parts_coverage", None),
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
        case_title = (
            (attempt.diagram_preset or {}).get("title")
            or (attempt.cloze_preset or {}).get("title")
            or (attempt.scenario_text.strip().split("\n")[0][:60].strip() if attempt.scenario_text else "")
            or attempt.case_type.replace("_", " ").capitalize()
        )
        for criterion in attempt.criteria:
            skill = criterion.get("skill_id") or criterion["criterion"]
            if skill.startswith("exercise:"):
                continue
            item = skills.setdefault(skill, {"skill_id": skill, "label": skill.replace("_", " ").capitalize(),
                "baseline": [], "revision": [], "transfer": [], "change_summary": "", "review_status": "provisional"})
            item[bucket].append({
                "attempt_id": attempt.id,
                "case_type": attempt.case_type,
                "support_level": attempt.support_level,
                "source_case_title": case_title,
                **criterion
            })
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
    journey_completed = (session.stage in ("review", "completed") and bool(expected_ids)
        and set(expected_ids) == baseline_done and any(a.stage == "apply" for a in attempts))
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
        outcome = "inconclusive"
        reason = ("The learning journey was completed, but some prepared criteria lack usable assessment evidence."
            if journey_completed else "The session ended before the complete independent case sequence was submitted."
            if session.stage in ("review", "completed") else "The learning journey is still in progress.")
        reason += " Saved answers remain available for review."
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

    has_technical_failure = any(c.get("rating") == "technical_failure" for c in all_rows)
    if has_technical_failure and not any("technical failure" in item.lower() for item in unresolved_items):
        unresolved_items.append("Assessment partially available due to technical failure")

    for b_skill in sorted(baseline_skills):
        if b_skill not in transfer_skills_all:
            label = b_skill.replace("_", " ").capitalize()
            if b_skill in baseline_concern_skills:
                unresolved_items.append(f"Earlier concern with '{label}' was not rechecked on unfamiliar case")
            else:
                unresolved_items.append(f"Skill '{label}' not rechecked on unfamiliar case")

    if concern_skills_not_rechecked:
        unresolved_items.append("Skills partially covered: earlier skills not retested on unfamiliar case")

    if not journey_completed:
        unresolved_items.append("Session is partial; remaining stages unassessed")
    unresolved_summary = "; ".join(unresolved_items) if unresolved_items else "None on tested cases. All tested criteria demonstrated; assessments remain provisional."

    support_counts = {}
    for i in interventions:
        kind = i.intervention_type.replace("_", " ").capitalize()
        support_counts[kind] = support_counts.get(kind, 0) + 1
    support_summary = ", ".join(f"{cnt} {k.lower()}" for k, cnt in support_counts.items()) if support_counts else "No external support recorded."

    # 5-point personal summary
    # 1. demonstrated: Concise summary of what the learner demonstrated across attempts.
    demonstrated_parts = []
    if transfer_demonstrated:
        t_labels = sorted({(c.get("skill_id") or c["criterion"]).replace("_", " ").capitalize() for c in transfer_demonstrated})
        demonstrated_parts.append(f"Demonstrated {len(transfer_demonstrated)} prepared criteria {support_desc} on the unfamiliar case: {', '.join(t_labels)}.")
    elif any(c.get("met") is True for c in baseline_criteria):
        b_labels = sorted({(c.get("skill_id") or c["criterion"]).replace("_", " ").capitalize() for c in baseline_criteria if c.get("met") is True})
        demonstrated_parts.append(f"Demonstrated initial reasoning on: {', '.join(b_labels)}.")
    else:
        demonstrated_parts.append("No criteria were clearly demonstrated in the evaluated responses.")
    personal_demonstrated = " ".join(demonstrated_parts)

    # 2. missing_or_incorrect: Concise summary of what was missing (omissions), incorrect (reasoning errors), or unclear (ambiguity).
    crit_issues = []
    all_evaluated = baseline_criteria + transfer_criteria
    omissions = [c for c in all_evaluated if c.get("rating") == "not_addressed" or c.get("issue_type") == "missing_requested_part"]
    incorrect_claims = [c for c in all_evaluated if c.get("issue_type") == "incorrect_claim"]
    incomplete_reasoning = [c for c in all_evaluated if c.get("rating") == "partially_demonstrated"
        and c.get("issue_type") not in ("incorrect_claim", "missing_requested_part")]
    ambiguities = [c for c in all_evaluated if (c.get("rating") == "ambiguous_needs_clarification" or c.get("met") is None) and c.get("rating") != "technical_failure"]
    if omissions:
        crit_issues.append("Omissions: " + ", ".join(sorted({(c.get("skill_id") or c["criterion"]).replace("_", " ") for c in omissions})))
    if incorrect_claims:
        crit_issues.append("Incorrect reasoning: " + ", ".join(sorted({(c.get("skill_id") or c["criterion"]).replace("_", " ") for c in incorrect_claims})))
    if incomplete_reasoning:
        crit_issues.append("Incomplete reasoning: " + ", ".join(sorted({(c.get("skill_id") or c["criterion"]).replace("_", " ") for c in incomplete_reasoning})))
    if ambiguities:
        crit_issues.append("Ambiguous explanations: " + ", ".join(sorted({(c.get("skill_id") or c["criterion"]).replace("_", " ") for c in ambiguities})))
    if has_technical_failure or transfer_missing or any(a.unavailable_criteria_count for a in baseline_attempts):
        crit_issues.append("Some assessment evidence is unavailable; no learner error is inferred for those criteria")
    personal_missing_or_incorrect = "; ".join(crit_issues) + "." if crit_issues else (
        "No omissions, incorrect claims, or ambiguous explanations detected in available assessments."
        if all_evaluated else "Assessment evidence is unavailable; omissions and incorrect claims cannot be determined.")

    # 3. changed_after_help: What changed after help (e.g. revision demonstrated criteria with tutor support vs completed independently).
    if revision_attempts:
        if revision_met:
            r_labels = sorted({(c.get("skill_id") or c["criterion"]).replace("_", " ") for c in revision_met})
            personal_changed_after_help = f"With tutor support, revised explanation successfully addressed: {', '.join(r_labels)}."
        else:
            personal_changed_after_help = "Revision was attempted with tutor support but did not resolve the identified criteria."
    elif interventions:
        personal_changed_after_help = "Support was consulted, but no revision attempt was submitted."
    else:
        personal_changed_after_help = "No tutor help or revision was requested."

    # 4. needs_independent_checking: What was demonstrated only with support, or skills not rechecked on fresh case, or remaining unmet transfer criteria.
    checking_items = []
    if not transfer_attempts:
        checking_items.append("Unfamiliar-case reasoning has not been submitted")
    elif not transfer_is_independent:
        checking_items.append("Independent unfamiliar-case evidence remains unestablished because support was used or is unknown")
    if transfer_technical_failures or transfer_missing:
        checking_items.append("Unfamiliar-case assessment is missing or unavailable and needs reassessment")
    if transfer_ambiguous:
        checking_items.append("Unfamiliar-case reasoning remains unclear and needs clarification")
    for s in revision_skills_met:
        transfer_s_met = any(c.get("skill_id") == s and c.get("met") is True for c in transfer_demonstrated)
        if not transfer_s_met or not transfer_is_independent:
            checking_items.append(f"{s.replace('_', ' ')} (demonstrated with support, needs independent recheck)")
    for s in concern_skills_not_rechecked:
        s_label = s.replace("_", " ")
        if not any(s_label in item for item in checking_items):
            checking_items.append(f"{s_label} (earlier difficulty not retested on unfamiliar case)")
    for c in transfer_unmet:
        s_label = (c.get("skill_id") or c["criterion"]).replace("_", " ")
        if not any(s_label in item for item in checking_items):
            checking_items.append(f"{s_label} (unmet on unfamiliar case)")
    personal_needs_checking = "; ".join(checking_items) + "." if checking_items else "None. All evaluated skills were independently demonstrated or rechecked."

    # 5. recommended_next_step: Concrete targeted next step / practice recommendation.
    if transfer_unmet:
        unmet_labels = sorted({(c.get("skill_id") or c["criterion"]).replace("_", " ") for c in transfer_unmet})
        personal_next_step = f"Practice applying {', '.join(unmet_labels)} in independent scenarios without assistance."
    elif not transfer_attempts:
        personal_next_step = "Complete an unfamiliar case independently before drawing a transfer conclusion."
    elif transfer_missing or has_technical_failure:
        personal_next_step = "Request reassessment for missing or unavailable criterion judgments."
    elif not transfer_is_independent:
        personal_next_step = "Complete a fresh unfamiliar case independently, with established support provenance."
    elif concern_skills_not_rechecked:
        unrechecked = sorted({s.replace("_", " ") for s in concern_skills_not_rechecked})
        personal_next_step = f"Complete a fresh case focusing on {', '.join(unrechecked)} to verify independent retention."
    elif transfer_ambiguous:
        amb_labels = sorted({(c.get("skill_id") or c["criterion"]).replace("_", " ") for c in transfer_ambiguous})
        personal_next_step = f"Clarify your reasoning on {', '.join(amb_labels)} with explicit cause-and-effect explanations."
    else:
        personal_next_step = "Continue to subsequent module concepts and apply these principles in project implementations."

    personal_summary = {
        "demonstrated": personal_demonstrated,
        "missing_or_incorrect": personal_missing_or_incorrect,
        "changed_after_help": personal_changed_after_help,
        "needs_independent_checking": personal_needs_checking,
        "recommended_next_step": personal_next_step,
    }

    # Build concern_cards
    # For each significant concern (unmet, partial, or unclear criteria in baseline or transfer):
    concern_cards = []
    seen_concerns = set()
    for a in reports:
        if a.stage not in ("diagnostic", "apply"):
            continue
        c_title = (
            (a.diagram_preset or {}).get("title")
            or (a.cloze_preset or {}).get("title")
            or (a.scenario_text.strip().split("\n")[0][:60].strip() if a.scenario_text else "")
            or a.case_type.replace("_", " ").capitalize()
        )
        qparts = a.question_parts or []
        qpart_map = {(p.get("id") or p.get("part_id")): p for p in qparts if isinstance(p, dict) and (p.get("id") or p.get("part_id"))}
        for c in a.criteria:
            if (c.get("skill_id") or "").startswith("exercise:"):
                continue
            rating = c.get("rating")
            met = c.get("met")
            is_concern = (rating in ("partially_demonstrated", "not_addressed", "ambiguous_needs_clarification", "technical_failure")) or (met is not True)
            if not is_concern:
                continue

            dedup_key = (a.id, c.get("criterion"))
            if dedup_key in seen_concerns:
                continue
            seen_concerns.add(dedup_key)

            qpart_id = c.get("question_part_id")
            qpart_obj = qpart_map.get(qpart_id) if qpart_id else None
            question_part_desc = (qpart_obj.get("description") if qpart_obj else None) or c.get("criterion")

            is_omitted = (rating == "not_addressed" or c.get("coverage") == "unanswered")
            quote = c.get("evidence") or ""
            learner_quote = quote if not is_omitted and rating != "technical_failure" and quote.casefold() in a.answer_text.casefold() else ""

            unavailable = rating == "technical_failure"
            what_was_correct = ("Assessment unavailable; demonstrated reasoning could not be determined."
                if unavailable else c.get("demonstrated_explanation") or "No specific demonstrated reasoning was recorded for this criterion.")
            why_rating = ("The assessment could not be completed; no learner mistake is inferred."
                if unavailable else c.get("explanation") or ("Omitted in the learner response." if is_omitted else "The response was incomplete or ambiguous."))
            next_act = c.get("next_action")
            how_to_improve = "Request reassessment of the saved answer." if unavailable else next_act or (
                f"Explain how you would {question_part_desc.lower()}." if is_omitted
                else f"State clearly what you meant regarding {c.get('criterion')}." if rating == "ambiguous_needs_clarification"
                else f"Clarify your reasoning regarding {c.get('criterion')}."
            )
            suggested_next_step = how_to_improve if unavailable else next_act or how_to_improve

            issue_type = "technical_failure" if unavailable else c.get("issue_type") or (
                "missing_requested_part" if is_omitted
                else "ambiguous_wording_or_interpretation" if rating == "ambiguous_needs_clarification"
                else "technical_failure" if rating == "technical_failure"
                else "insufficient_evidence"
            )

            concern_cards.append({
                "case_name": c_title,
                "question_part": question_part_desc,
                "learner_quote": learner_quote,
                "what_was_correct": what_was_correct,
                "why_rating": why_rating,
                "how_to_improve": how_to_improve,
                "suggested_next_step": suggested_next_step,
                "issue_type": issue_type,
                "rating": rating,
            })

    session_summary = {
        "completion_reason": "journey_completed" if journey_completed else "ended_before_unfamiliar_submission"
            if session.stage in ("review", "completed") else "in_progress",
        "unfamiliar_case_summary": unfamiliar_summary,
        "revised_reasoning_summary": revised_summary,
        "unresolved_summary": unresolved_summary,
        "support_summary": support_summary,
        "personal_summary": personal_summary,
        "concern_cards": concern_cards,
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

