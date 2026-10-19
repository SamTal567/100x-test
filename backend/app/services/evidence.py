"""Prepared exercise checks and immutable attempt evidence (no model decisions)."""
from copy import deepcopy
import json


def snapshot_case(case):
    rubric = case.rubric
    return deepcopy({"id": case.id, "version": case.version, "stage": case.stage,
        "case_type": case.case_type, "scenario_text": case.scenario_text,
        "response_format": case.response_format, "assumptions": case.assumptions,
        "diagram_preset": case.diagram_preset, "cloze_preset": case.cloze_preset,
        "question_parts": getattr(case, "question_parts", None),
        "review_status": case.review_status,
        "rubric": {"version": rubric.version, "reference_answer": rubric.reference_answer,
            "criteria": rubric.criteria} if rubric else {}})


def assessment_answer(attempt):
    parts = [attempt.answer_text]
    if attempt.diagram_state is not None:
        parts.append("Learner diagram selections: " + json.dumps(attempt.diagram_state, sort_keys=True))
    if attempt.cloze_state is not None:
        parts.append("Learner cloze selections: " + json.dumps(attempt.cloze_state, sort_keys=True))
    return "\n".join(parts)


def validate_exercise(case, turn):
    """Reject selections outside the authored options, never trust client correctness flags."""
    for preset, state in [(case.diagram_preset, turn.diagram_state), (case.cloze_preset, turn.cloze_state)]:
        if state is None:
            continue
        if not preset:
            raise ValueError("Exercise selections do not belong to the current prompt")
        if "repair_options" in preset:
            choices = [state[key] for key in ("repair_selection", "selected_repair", "selected_option", "selected_option_id") if key in state]
            if "selected_target" in state:
                target = state["selected_target"]
                matches = [o["id"] for o in preset["repair_options"] if o.get("target_node") == target]
                if len(matches) != 1:
                    raise ValueError("Invalid diagram target selection")
                choices.extend(matches)
            for choice in choices:
                if not isinstance(choice, str) or choice not in {o["id"] for o in preset["repair_options"]}:
                    raise ValueError("Invalid diagram repair selection")
            if len(set(choices)) > 1:
                raise ValueError("Conflicting diagram repair selections")
        blanks = {b["id"]: b for b in preset.get("blanks", [])}
        values = state.get("blanks", state)
        if not isinstance(values, dict):
            raise ValueError("Exercise blanks must be an object keyed by blank ID")
        if "selected_blank" in state:
            blank_id = state.get("blank_id")
            if blank_id not in blanks or state["selected_blank"] not in blanks[blank_id].get("options", []):
                raise ValueError("Invalid diagram blank selection")
        for key, value in values.items():
            if key in blanks and value not in blanks[key].get("options", []):
                raise ValueError("Invalid exercise option")
        allowed = set(blanks) | {"repair_selection", "selected_repair", "selected_target", "selected_blank", "blank_id", "interaction", "selected_option", "selected_option_id", "selected_steps", "selected_edges", "selected_nodes", "trace", "blanks"}
        if set(state) - allowed:
            raise ValueError("Unexpected exercise selection fields")
        if "blanks" in state and set(values) - set(blanks):
            raise ValueError("Unknown exercise blank ID")


def exercise_results(snapshot, diagram_state, cloze_state):
    """Objective selection evidence is separate from conceptual reasoning criteria."""
    rows = []
    for kind, preset, state in [("diagram", snapshot.get("diagram_preset"), diagram_state),
                                ("cloze", snapshot.get("cloze_preset"), cloze_state)]:
        if not preset:
            continue
        state = state or {}
        if "correct_repair" in preset:
            selected = state.get("repair_selection", state.get("selected_repair", state.get("selected_option", state.get("selected_option_id"))))
            if selected is None and "selected_target" in state:
                selected = next((o["id"] for o in preset.get("repair_options", []) if o.get("target_node") == state["selected_target"]), None)
            met = selected == preset["correct_repair"] if selected is not None else None
            rows.append({"criterion": "Diagram repair selection", "skill_id": "exercise:diagram_repair",
                "rating": "demonstrated" if met else "not_addressed" if selected is None else "partially_demonstrated",
                "met": met, "evidence": f"Selected option: {selected or 'not submitted'}. Selection accuracy only; reasoning is assessed separately."})
        selections = state.get("blanks", state)
        for blank in preset.get("blanks", []):
            value = selections.get(blank["id"])
            if value is None and state.get("blank_id") == blank["id"]:
                value = state.get("selected_blank")
            correct = blank.get("correct")
            accepted = correct if isinstance(correct, list) else [correct]
            met = value in accepted if value is not None else None
            rows.append({"criterion": f"{kind.title()} selection: {blank['id']}",
                "skill_id": f"exercise:{kind}:{blank['id']}",
                "rating": "demonstrated" if met else "not_addressed" if value is None else "partially_demonstrated",
                "met": met, "evidence": f"Selected: {value or 'not submitted'}. Selection accuracy only; reasoning is assessed separately."})
    return rows


class NormalizedProposal(tuple):
    """3-tuple compatible proposal with rich question-part assessment fields."""
    def __new__(cls, met, rating, evidence,
                question_part_id=None, coverage=None, issue_type=None,
                demonstrated_explanation=None, explanation=None, next_action=None):
        instance = super().__new__(cls, (met, rating, evidence))
        instance.met = met
        instance.rating = rating
        instance.evidence = evidence
        instance.question_part_id = question_part_id
        instance.coverage = coverage
        instance.issue_type = issue_type
        instance.demonstrated_explanation = demonstrated_explanation
        instance.explanation = explanation
        instance.next_action = next_action
        return instance


def normalized_proposal(proposed, answer, result_status, summary="", question_parts=None, criterion_id=None):
    if proposed is None or result_status != "complete":
        msg = summary or "Assessment was unavailable or did not return this prepared criterion exactly once."
        return NormalizedProposal(
            None, "technical_failure", msg,
            issue_type="technical_failure",
            explanation=msg,
            next_action="Request reassessment or consult the tutor for guidance."
        )

    rating = getattr(proposed, "rating", None)
    met = getattr(proposed, "met", None)
    evidence = (getattr(proposed, "evidence", "") or "").strip()
    question_part_id = getattr(proposed, "question_part_id", None)
    coverage = getattr(proposed, "coverage", None)
    issue_type = getattr(proposed, "issue_type", None)
    demonstrated_explanation = getattr(proposed, "demonstrated_explanation", None)
    explanation = getattr(proposed, "explanation", None)
    next_action = getattr(proposed, "next_action", None)

    # Validate / match question_part_id against question_parts
    part_desc = None
    if question_parts and isinstance(question_parts, list):
        part_map = {p["id"]: p for p in question_parts if isinstance(p, dict) and "id" in p}
        if question_part_id and question_part_id in part_map:
            part_desc = part_map[question_part_id].get("description")
        else:
            matching_parts = [
                p for p in question_parts
                if isinstance(p, dict) and criterion_id and (criterion_id in p.get("criterion_ids", []))
            ]
            if len(matching_parts) == 1:
                question_part_id = matching_parts[0]["id"]
                part_desc = matching_parts[0].get("description")
            else:
                question_part_id = None
                part_desc = None

    expected = {
        "demonstrated": True,
        "partially_demonstrated": False,
        "not_addressed": False,
        "ambiguous_needs_clarification": None,
        "technical_failure": None,
    }

    if rating not in expected or met is not expected[rating]:
        return NormalizedProposal(
            None, "technical_failure",
            "Provider returned an inconsistent rating and verdict; reviewer assessment is needed.",
            question_part_id=question_part_id,
            issue_type="technical_failure",
            explanation="Provider returned an inconsistent rating and verdict; reviewer assessment is needed.",
            next_action="Reviewer evaluation is needed."
        )

    if rating == "technical_failure":
        return NormalizedProposal(
            None, rating, evidence or "Provider could not assess this criterion.",
            question_part_id=question_part_id,
            issue_type="technical_failure",
            explanation=explanation or evidence or "Provider could not assess this criterion.",
            next_action=next_action or "Request reassessment or consult the tutor."
        )

    if rating == "not_addressed" or issue_type == "missing_requested_part":
        missing_desc = part_desc or (f"address {criterion_id}" if criterion_id else "address this requirement")
        if not explanation or not explanation.strip().startswith("You did not answer"):
            explanation = f"You did not answer the part asking you to {missing_desc}."
        action = next_action or (f"Explain how you would {missing_desc}." if part_desc else "State your reasoning on this point.")
        return NormalizedProposal(
            False, "not_addressed", "",
            question_part_id=question_part_id,
            coverage=coverage or "unanswered",
            issue_type="missing_requested_part",
            demonstrated_explanation=demonstrated_explanation,
            explanation=explanation,
            next_action=action
        )

    if met is not None and (not evidence or evidence.casefold() not in answer.casefold()):
        return NormalizedProposal(
            None, "ambiguous_needs_clarification",
            "Assessment evidence could not be verified in the submitted answer.",
            question_part_id=question_part_id,
            coverage="unclear",
            issue_type="insufficient_evidence",
            demonstrated_explanation=demonstrated_explanation,
            explanation=explanation or "Assessment evidence could not be verified in the submitted answer.",
            next_action=next_action or "Clarify your answer with specific reasoning from the scenario."
        )

    if rating == "demonstrated":
        cov = coverage or "answered"
        it = None
        exp = explanation or "Demonstrated accurate reasoning according to the prepared criteria."
        act = next_action or "Continue to apply this understanding."
    elif rating == "partially_demonstrated":
        cov = coverage or "partly_answered"
        it = issue_type if issue_type in ("incorrect_claim", "missing_requested_part", "ambiguous_wording_or_interpretation", "insufficient_evidence") else "incorrect_claim"
        exp = explanation or "Your response partly answered this requirement but needs further development."
        act = next_action or "Clarify your reasoning and address the remaining parts."
    else:  # ambiguous_needs_clarification
        cov = coverage or "unclear"
        it = issue_type if issue_type in ("ambiguous_wording_or_interpretation", "insufficient_evidence") else "ambiguous_wording_or_interpretation"
        exp = explanation or "Your reasoning was ambiguous and needs clarification."
        act = next_action or "State clearly what you meant in your explanation."

    return NormalizedProposal(
        met, rating, evidence,
        question_part_id=question_part_id,
        coverage=cov,
        issue_type=it,
        demonstrated_explanation=demonstrated_explanation,
        explanation=exp,
        next_action=act
    )
