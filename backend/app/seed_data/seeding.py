"""Version prepared cases without changing evidence behind a saved attempt.

Only known authored identities and recognised legacy seed scenarios are managed.
User-created rows, including other AI-authored questions, remain untouched.
"""

import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import CasePrompt, CaseReviewRevision, Concept, Rubric
from app.seed_data import CASE_BANKS, CONCEPTS, STORAGE_PERSISTENCE_CASES


CASE_FIELDS = (
    "stage", "case_type", "scenario_text", "sort_order", "response_format",
    "assumptions", "diagram_preset", "cloze_preset", "question_parts",
)

# Exact introductory paragraphs from shipped seed files. Do not retire arbitrary
# rows by sort order, source alone, or a broad phrase such as "A game server".
LEGACY_STORAGE_INTRODUCTIONS = {
    c["scenario_text"].split("\n\n")[0] for c in STORAGE_PERSISTENCE_CASES
} | {
    "A game server keeps each player's score in a dictionary during the match. Scores are written to a database only when the match ends. The server crashes mid-match. What happens to the scores?",
    "An e-commerce site caches product prices in memory for speed. A price update is made in the database, but the cache isn't refreshed. Then the server restarts. After restart, does the customer see the old or new price? Why?",
    "A logging service writes each log entry to both an in-memory buffer and a log file on disk. The buffer holds the 100 most recent entries for quick display. The server restarts. Describe what the admin sees when they open the log viewer.",
}


def _fingerprint(data, rubric):
    """Review labels are provenance, not authored semantic content to reset."""
    body = {field: data.get(field) for field in CASE_FIELDS}
    body["rubric"] = {
        "reference_answer": rubric["reference_answer"], "criteria": rubric["criteria"],
    }
    serialised = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def _existing_fingerprint(row):
    if row.rubric is None:
        return None
    return _fingerprint(
        {field: getattr(row, field) for field in CASE_FIELDS},
        {"reference_answer": row.rubric.reference_answer, "criteria": row.rubric.criteria},
    )


def _validate_bank(slug, cases):
    """Fail startup on incomplete managed content instead of enabling empty topics."""
    groups = {kind: [c for c in cases if c["case_type"] == kind]
              for kind in ("baseline", "guided_practice", "transfer", "confirmation")}
    if len(groups["baseline"]) < 2 or len(groups["guided_practice"]) < 2 or len(groups["transfer"]) < 2 or not groups["confirmation"]:
        raise ValueError(f"Incomplete prepared progression for {slug}")
    ids = [c["authored_id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate authored case identity for {slug}")
    baseline_skills = {r["skill_id"] for c in groups["baseline"] for r in c["rubric"]["criteria"]}
    transfer_skills = {r["skill_id"] for c in groups["transfer"] for r in c["rubric"]["criteria"]}
    if baseline_skills != transfer_skills:
        raise ValueError(f"Unmatched baseline/transfer skills for {slug}")
    for case in cases:
        if not case["assumptions"] or not case["rubric"]["reference_answer"]:
            raise ValueError(f"Missing prepared assumptions or key for {slug}")
        if not case.get("question_parts"):
            raise ValueError(f"Missing question parts for {case.get('authored_id', slug)}")


def seed_authored_data(db: Session, case_banks=None):
    """Commit an idempotent catalogue seed; never mutate a case/rubric snapshot.

    A substantive change gets a new case and rubric, with a new immutable UUID
    derived from the authored identity and content hash. Prior sessions continue
    referencing their original rows even when those rows are inactive for new
    sessions. An exact previous version can be reactivated without rewriting it
    only while the lineage is seed-managed. A recorded human review transfers
    that lineage's activation/content decisions to the reviewer. Startup does
    not override even an inactive rejection with a shipped question; a later
    authored upgrade needs an explicit review decision outside this seed path.
    """
    banks = CASE_BANKS if case_banks is None else case_banks
    try:
        for slug, cases in banks.items():
            _validate_bank(slug, cases)
        for concept_data in CONCEPTS:
            slug = concept_data["slug"]
            concept = db.query(Concept).filter_by(slug=slug).first()
            data = dict(concept_data)
            data["enabled"] = slug in banks
            if concept is None:
                concept = Concept(id=str(uuid5(NAMESPACE_URL, f"concept-check/concept/{slug}")), **data)
                db.add(concept)
            else:
                # Catalogue descriptions are not attempt evidence; cases/keys are.
                for field, value in data.items():
                    setattr(concept, field, value)
            db.flush()

            for authored in banks.get(slug, []):
                identity = authored["authored_id"]
                rubric = authored["rubric"]
                fingerprint = _fingerprint(authored, rubric)
                versions = db.query(CasePrompt).filter_by(concept_id=concept.id, authored_id=identity).all()
                version_ids = [version.id for version in versions]
                if version_ids and db.query(CaseReviewRevision.id).filter(or_(
                    CaseReviewRevision.source_case_id.in_(version_ids),
                    CaseReviewRevision.reviewed_case_id.in_(version_ids),
                )).first() is not None:
                    # A rejected replacement is deliberately inactive. Looking
                    # only for an active/reviewed row would revive its ancestor
                    # or silently install an unapproved shipped update.
                    continue
                target = next((v for v in versions if _existing_fingerprint(v) == fingerprint), None)
                if target is None:
                    version = max((v.version for v in versions), default=0) + 1
                    case_id = str(uuid5(NAMESPACE_URL, f"concept-check/version/{identity}/{fingerprint}"))
                    target = CasePrompt(
                        id=case_id, concept_id=concept.id, authored_id=identity, version=version,
                        source=authored.get("source", "ai-authored"),
                        review_status=authored.get("review_status", "unreviewed"), active=True,
                        **{field: authored.get(field) for field in CASE_FIELDS},
                    )
                    db.add(target)
                    db.flush()
                    db.add(Rubric(
                        id=str(uuid5(NAMESPACE_URL, f"concept-check/rubric/{case_id}")),
                        case_prompt_id=case_id, version=version,
                        reference_answer=rubric["reference_answer"], criteria=rubric["criteria"],
                    ))
                target.active = True
                for previous in versions:
                    if previous.id != target.id:
                        previous.active = False

            if slug == "storage-persistence":
                legacy_rows = db.query(CasePrompt).filter_by(
                    concept_id=concept.id, authored_id=None, source="ai-authored",
                ).all()
                for legacy in legacy_rows:
                    if legacy.scenario_text.split("\n\n")[0] in LEGACY_STORAGE_INTRODUCTIONS:
                        legacy.active = False
        db.commit()
    except Exception:
        db.rollback()
        raise
