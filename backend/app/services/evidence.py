"""Prepared exercise checks and immutable attempt evidence (no model decisions)."""
from copy import deepcopy
import json


def snapshot_case(case):
    rubric = case.rubric
    return deepcopy({"id": case.id, "version": case.version, "stage": case.stage,
        "case_type": case.case_type, "scenario_text": case.scenario_text,
        "response_format": case.response_format, "assumptions": case.assumptions,
        "diagram_preset": case.diagram_preset, "cloze_preset": case.cloze_preset,
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


def normalized_proposal(proposed, answer, result_status, summary=""):
    if proposed is None or result_status != "complete":
        return None, "technical_failure", summary or "Assessment was unavailable or did not return this prepared criterion exactly once."
    rating, met, evidence = proposed.rating, proposed.met, proposed.evidence or ""
    expected = {"demonstrated": True, "partially_demonstrated": False,
        "not_addressed": False, "ambiguous_needs_clarification": None, "technical_failure": None}
    if rating not in expected or met is not expected[rating]:
        return None, "technical_failure", "Provider returned an inconsistent rating and verdict; reviewer assessment is needed."
    if rating == "technical_failure":
        return None, rating, evidence or "Provider could not assess this criterion."
    if rating == "not_addressed":
        return False, rating, "Concept not addressed in learner response. An omission alone does not establish a misconception."
    if met is not None and (not evidence.strip() or evidence.casefold() not in answer.casefold()):
        return None, "ambiguous_needs_clarification", "Assessment evidence could not be verified in the submitted answer."
    return met, rating, evidence
