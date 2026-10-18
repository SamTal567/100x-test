"""Opt-in live provider smoke check. Fictional inputs only; never reads learner records."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.adapters.openai_adapter import OpenAIAdapter


async def check():
    adapter = OpenAIAdapter()
    if not adapter.available:
        print(json.dumps({"configured": False, "result": "unavailable", "requests": 0}))
        return 1
    scenario = "A server appends a note only to a Python list, then restarts with an empty list. No file or database write occurs. Does the note survive? Explain why."
    reference = "No. Process memory does not survive a restart; the note would need a committed write to persistent storage and a retrieval path."
    criteria = [{"criterion": "Explains process memory lifetime", "skill_id": "memory_lifetime", "description": "States that the process-owned list is lost when the process terminates."}]
    correct = "No. The list exists only in process memory, which is lost on restart. A new process starts empty."
    incorrect = "Yes. A Python list automatically survives a server restart, so the new process will retrieve the old note."
    result = {"configured": True, "fictional_smoke_check": True, "requests": 0}
    good = await adapter.assess_attempt(scenario, correct, reference, criteria)
    result["requests"] += 1
    result["correct_answer"] = good.model_dump()
    if good.status != "complete":
        print(json.dumps(result, indent=2))
        return 1
    bad = await adapter.assess_attempt(scenario, incorrect, reference, criteria)
    gap = await adapter.analyse_answer(scenario, incorrect, reference, criteria)
    tutor = await adapter.tutor_conversation(scenario, ["No persistent write occurs."], incorrect,
        gap.description, gap.probe_question, [], "request_teaching", "Please explain with an ASCII diagram.")
    result.update(requests=4, incorrect_answer=bad.model_dump(), gap=gap.model_dump(), tutor=tutor.model_dump())
    result["checks"] = {"correct_reasoning_met": bool(good.criteria and good.criteria[0].met is True),
        "incorrect_reasoning_not_met": bool(bad.criteria and bad.criteria[0].met is False and bad.criteria[0].rating == "partially_demonstrated" and bad.criteria[0].evidence.lower() in incorrect.lower()),
        "gap_quote_verified": bool(gap.status == "complete" and gap.gap_found and gap.evidence_quote.lower() in incorrect.lower()),
        "tutor_has_ascii": tutor.status == "complete" and "```" in tutor.message}
    print(json.dumps(result, indent=2))
    return 0 if all(result["checks"].values()) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Make up to four billable calls using backend configuration")
    if not parser.parse_args().live:
        parser.error("Pass --live to explicitly run provider requests")
    raise SystemExit(asyncio.run(check()))
