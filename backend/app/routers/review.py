"""Attachments download and Review API routers."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DBSession

from app.db.database import get_db
from app.db.models import (
    Attachment, CriterionAssessment, Attempt, AssessmentReviewRevision,
    CasePrompt, Rubric, CaseReviewRevision,
)
from app.schemas import AssessmentReviewItem, AssessmentReviewSubmit, CaseReviewSubmit
from app.auth import get_owner_id

from datetime import datetime, timezone
import os
import secrets
import copy

# ── Attachments ──────────────────────────────────────────────────

attachments_router = APIRouter(prefix="/v1/attachments", tags=["attachments"])


@attachments_router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: str,
    owner_id: str = Depends(get_owner_id),
    db: DBSession = Depends(get_db),
):
    """Download an owned attachment."""
    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "Attachment not found")
    if attachment.owner_id != owner_id:
        raise HTTPException(403, "Access denied")
    if not os.path.exists(attachment.storage_path):
        raise HTTPException(404, "File not found on disk")

    return FileResponse(
        attachment.storage_path,
        media_type=attachment.content_type,
        filename=attachment.filename,
    )


from app.config import get_settings
from fastapi import Header

# ── Review ───────────────────────────────────────────────────────

review_router = APIRouter(prefix="/v1/review", tags=["review"])


def verify_reviewer_auth(x_reviewer_key: str = Header(None, alias="X-Reviewer-Key")):
    """Server-validated reviewer authorization. Fails closed."""
    settings = get_settings()
    configured_key = settings.reviewer_api_key.strip()
    if not configured_key or not x_reviewer_key or not secrets.compare_digest(x_reviewer_key.strip().encode("utf-8"), configured_key.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Reviewer authorization required. Provide a valid X-Reviewer-Key header.")
    return True


@review_router.get("/assessments", response_model=list[AssessmentReviewItem])
def list_assessments_for_review(
    _auth: bool = Depends(verify_reviewer_auth),
    db: DBSession = Depends(get_db),
):
    """List provisional assessments awaiting review with full attempt context.

    Protected by server-validated X-Reviewer-Key header.
    """
    assessments = (
        db.query(CriterionAssessment)
        .filter(CriterionAssessment.status.in_(["provisional", "reviewed", "corrected"]))
        .order_by(CriterionAssessment.created_at.desc())
        .limit(100)
        .all()
    )

    items = []
    for ca in assessments:
        attempt = db.get(Attempt, ca.attempt_id)
        case = attempt.case_prompt if attempt else None
        rubric = case.rubric if case else None
        snapshot = attempt.case_snapshot or {} if attempt else {}
        rubric_snapshot = snapshot.get("rubric") or {}
        revisions = (
            db.query(AssessmentReviewRevision).filter_by(assessment_id=ca.id)
            .order_by(AssessmentReviewRevision.created_at, AssessmentReviewRevision.id).all()
        )

        items.append(
            AssessmentReviewItem(
                id=ca.id,
                attempt_id=ca.attempt_id,
                criterion=ca.criterion,
                skill_id=ca.skill_id,
                rating=ca.rating,
                status=ca.status,
                met=ca.met,
                evidence=ca.evidence,
                scenario_text=snapshot.get("scenario_text", case.scenario_text if case else ""),
                answer_text=attempt.answer_text if attempt else "",
                diagram_state=attempt.diagram_state if attempt else None,
                reference_answer=rubric_snapshot.get("reference_answer", snapshot.get("reference_answer", rubric.reference_answer if rubric else "")),
                reviewer_notes=ca.reviewer_notes,
                case_prompt_id=attempt.case_prompt_id if attempt else None,
                case_version=snapshot.get("version", case.version if case else None),
                rubric_version=attempt.rubric_version if attempt else None,
                diagram_preset=snapshot.get("diagram_preset", case.diagram_preset if case else None),
                cloze_preset=snapshot.get("cloze_preset", case.cloze_preset if case else None),
                cloze_state=attempt.cloze_state if attempt else None,
                proposal=revisions[0].proposal_snapshot if revisions else _assessment_snapshot(ca),
                review_history=[{
                    "id": rev.id, "reviewer_name": rev.reviewer_name,
                    "created_at": rev.created_at.isoformat(),
                    "previous": rev.previous_snapshot, "review": rev.review_snapshot,
                } for rev in revisions],
            )
        )
    return items


@review_router.post("/assessments/{assessment_id}")
def review_assessment(
    assessment_id: str,
    body: AssessmentReviewSubmit,
    _auth: bool = Depends(verify_reviewer_auth),
    db: DBSession = Depends(get_db),
):
    """Submit an authorized review for a criterion assessment."""
    assessment = db.get(CriterionAssessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    if body.rating is None and "met" not in body.model_fields_set:
        expected_met = (True if assessment.rating == "demonstrated" else
                        False if assessment.rating in {"partially_demonstrated", "not_addressed"} else None)
        if assessment.met is not expected_met:
            raise HTTPException(422, "Legacy rating and met disagree; provide an explicit corrected rating.")

    previous = _assessment_snapshot(assessment)
    first_revision = (
        db.query(AssessmentReviewRevision).filter_by(assessment_id=assessment.id)
        .order_by(AssessmentReviewRevision.created_at, AssessmentReviewRevision.id).first()
    )
    proposal = first_revision.proposal_snapshot if first_revision else previous
    assessment.status = body.status
    if body.rating is not None:
        assessment.rating = body.rating
        assessment.met = (True if body.rating == "demonstrated" else
                          False if body.rating in {"partially_demonstrated", "not_addressed"} else None)
    elif "met" in body.model_fields_set:
        assessment.met = body.met
        assessment.rating = ("demonstrated" if body.met is True else
                             "not_addressed" if body.met is False else "ambiguous_needs_clarification")
    if "reviewer_notes" in body.model_fields_set:
        assessment.reviewer_notes = body.reviewer_notes
    assessment.reviewed_at = datetime.now(timezone.utc)
    revision = AssessmentReviewRevision(
        assessment_id=assessment.id,
        reviewer_name=body.reviewer_name.strip(),
        proposal_snapshot=copy.deepcopy(proposal),
        previous_snapshot=previous,
        review_snapshot=_assessment_snapshot(assessment),
    )
    db.add(revision)

    db.commit()
    return {"status": "ok", "assessment_id": assessment_id, "revision_id": revision.id}


def _assessment_snapshot(assessment: CriterionAssessment) -> dict:
    return {
        "rating": assessment.rating, "met": assessment.met,
        "status": assessment.status, "evidence": assessment.evidence,
        "reviewer_notes": assessment.reviewer_notes,
    }


@review_router.get("/cases")
def list_cases_for_review(
    _auth: bool = Depends(verify_reviewer_auth),
    db: DBSession = Depends(get_db),
):
    """Private authoring desk: original keys and case/rubric versions for review."""
    cases = db.query(CasePrompt).order_by(CasePrompt.concept_id, CasePrompt.sort_order, CasePrompt.version.desc()).all()
    return [{
        "id": case.id, "authored_id": case.authored_id,
        "concept_id": case.concept_id, "stage": case.stage,
        "case_type": case.case_type, "version": case.version,
        "active": case.active, "review_status": case.review_status,
        "scenario_text": case.scenario_text, "assumptions": case.assumptions,
        "response_format": case.response_format,
        "diagram_preset": case.diagram_preset, "cloze_preset": case.cloze_preset,
        "reference_answer": case.rubric.reference_answer if case.rubric else "",
        "criteria": case.rubric.criteria if case.rubric else [],
        "rubric_version": case.rubric.version if case.rubric else None,
    } for case in cases]


@review_router.post("/cases/{case_id}")
def review_case(
    case_id: str,
    body: CaseReviewSubmit,
    _auth: bool = Depends(verify_reviewer_auth),
    db: DBSession = Depends(get_db),
):
    """Review by creating a new immutable version; prior session references survive."""
    original = db.get(CasePrompt, case_id)
    if not original:
        raise HTTPException(404, "Case not found")
    if not original.active:
        raise HTTPException(409, "Review the current active version of this case.")
    source_rubric = original.rubric
    if not source_rubric:
        raise HTTPException(409, "Case requires a prepared rubric before review.")
    values = {name: copy.deepcopy(getattr(original, name)) for name in (
        "concept_id", "authored_id", "stage", "case_type", "scenario_text",
        "sort_order", "source", "response_format", "assumptions", "diagram_preset", "cloze_preset",
    )}
    for name in ("scenario_text", "assumptions", "diagram_preset", "cloze_preset"):
        if name in body.model_fields_set:
            if name == "scenario_text" and body.scenario_text is None:
                raise HTTPException(422, "Scenario must not be empty.")
            values[name] = copy.deepcopy(getattr(body, name))
    replacement = CasePrompt(
        **values, version=original.version + 1,
        review_status=body.review_status, active=body.review_status == "reviewed",
    )
    reserved = db.query(CasePrompt).filter_by(id=original.id, active=True, version=original.version).update(
        {"active": False}, synchronize_session=False,
    )
    if reserved != 1:
        db.rollback()
        raise HTTPException(409, "Case version changed; reload before reviewing.")
    db.add(replacement)
    db.flush()
    db.add(Rubric(
        case_prompt_id=replacement.id, version=source_rubric.version + 1,
        reference_answer=body.reference_answer or source_rubric.reference_answer,
        criteria=copy.deepcopy(body.criteria if body.criteria is not None else source_rubric.criteria),
    ))
    revision = CaseReviewRevision(
        source_case_id=original.id, reviewed_case_id=replacement.id,
        reviewer_name=body.reviewer_name, review_status=body.review_status,
        reviewer_notes=body.reviewer_notes,
    )
    db.add(revision)
    db.commit()
    return {"status": "ok", "case_id": replacement.id, "version": replacement.version,
            "review_status": replacement.review_status, "revision_id": revision.id}
