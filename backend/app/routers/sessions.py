"""Sessions API router."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session as DBSession

from app.db.database import get_db
from app.db.models import (
    Session, CasePrompt, Concept, Attachment, Transcription,
    TurnIdempotency,
)
from app.schemas import (
    SessionCreate, SessionOut, SessionListItem, CasePromptOut,
    TurnRequest, TurnResponse, SessionReport,
    TranscriptionOut, AttachmentOut,
)
from app.auth import get_owner_id
from app.services.session_service import SessionService
from app.adapters.fish_audio_adapter import get_fish_audio_adapter

import os
import uuid

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])

# Local upload directory for attachments/audio
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("", response_model=SessionOut, status_code=201)
def create_session(
    body: SessionCreate,
    owner_id: str = Depends(get_owner_id),
    db: DBSession = Depends(get_db),
):
    """Create a new learning session for a concept."""
    concept = db.get(Concept, body.concept_id)
    if not concept:
        raise HTTPException(404, "Concept not found")
    if not concept.enabled:
        raise HTTPException(400, "Concept is not yet available")

    # Freeze case IDs so later authored/reviewed versions do not alter this baseline.
    baseline_cases = (
        db.query(CasePrompt)
        .filter_by(concept_id=concept.id, stage="diagnostic", case_type="baseline", active=True)
        .filter(CasePrompt.review_status != "rejected")
        .order_by(CasePrompt.sort_order, CasePrompt.id)
        .all()
    )
    if not baseline_cases:
        raise HTTPException(409, "No active baseline cases are available for this concept.")
    first_case = baseline_cases[0]

    session = Session(
        owner_id=owner_id,
        concept_id=concept.id,
        stage="diagnostic",
        current_prompt_id=first_case.id if first_case else None,
        diagnostic_index=0,
        baseline_prompt_ids=[case.id for case in baseline_cases],
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return _session_to_out(session, db)


@router.get("", response_model=list[SessionListItem])
def list_sessions(
    owner_id: str = Depends(get_owner_id),
    db: DBSession = Depends(get_db),
):
    """List all sessions for the current user."""
    sessions = (
        db.query(Session)
        .filter_by(owner_id=owner_id)
        .order_by(Session.updated_at.desc())
        .all()
    )
    result = []
    for s in sessions:
        concept = db.get(Concept, s.concept_id)
        result.append(SessionListItem(
            id=s.id,
            concept_id=s.concept_id,
            concept_title=concept.title if concept else "",
            stage=s.stage,
            created_at=s.created_at,
            updated_at=s.updated_at,
        ))
    return result


@router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: str,
    owner_id: str = Depends(get_owner_id),
    db: DBSession = Depends(get_db),
):
    """Get hydrated session detail. Scoped to the current owner."""
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.owner_id != owner_id:
        raise HTTPException(403, "Access denied")

    return _session_to_out(session, db)


@router.post("/{session_id}/turns", response_model=TurnResponse)
async def submit_turn(
    session_id: str,
    body: TurnRequest,
    owner_id: str = Depends(get_owner_id),
    db: DBSession = Depends(get_db),
):
    """Submit a turn (answer, clarification, etc.)."""
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.owner_id != owner_id:
        raise HTTPException(403, "Access denied")

    service = SessionService(db)
    try:
        return await service.process_turn(session, body, owner_id)
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.get("/{session_id}/report", response_model=SessionReport)
def get_report(
    session_id: str,
    owner_id: str = Depends(get_owner_id),
    db: DBSession = Depends(get_db),
):
    """Get the session report."""
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.owner_id != owner_id:
        raise HTTPException(403, "Access denied")

    service = SessionService(db)
    return service.generate_report(session)


@router.post("/{session_id}/transcriptions", response_model=TranscriptionOut, status_code=201)
async def upload_transcription(
    session_id: str,
    audio: UploadFile = File(...),
    owner_id: str = Depends(get_owner_id),
    db: DBSession = Depends(get_db),
):
    """Upload audio for speech-to-text transcription.

    Returns the transcription for the learner to review and confirm.
    Does NOT automatically submit an answer.
    """
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.owner_id != owner_id:
        raise HTTPException(403, "Access denied")

    # Read audio data
    audio_bytes = await audio.read()

    # Create transcription record
    transcription = Transcription(
        session_id=session_id,
        owner_id=owner_id,
        status="pending",
    )
    db.add(transcription)
    db.flush()

    # Call Fish Audio adapter
    adapter = get_fish_audio_adapter()
    result = await adapter.transcribe(
        audio_bytes=audio_bytes,
        filename=audio.filename or "recording.webm",
        content_type=audio.content_type or "audio/webm",
    )

    if result["success"]:
        transcription.raw_transcript = result["transcript"]
        transcription.audio_duration_ms = result["duration_ms"]
        transcription.status = "transcribed"
    else:
        transcription.status = "failed"
        # Still return the record so the frontend knows what happened

    db.commit()
    db.refresh(transcription)

    if not result["success"]:
        raise HTTPException(
            status_code=503 if "unavailable" in (result.get("error") or "").lower() else 500,
            detail=result["error"],
        )

    return TranscriptionOut.model_validate(transcription)


@router.post("/{session_id}/attachments", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    session_id: str,
    file: UploadFile = File(...),
    owner_id: str = Depends(get_owner_id),
    db: DBSession = Depends(get_db),
):
    """Upload an attachment (image, diagram, etc.)."""
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.owner_id != owner_id:
        raise HTTPException(403, "Access denied")

    file_bytes = await file.read()
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or "")[1] or ".bin"
    storage_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")

    with open(storage_path, "wb") as f:
        f.write(file_bytes)

    attachment = Attachment(
        id=file_id,
        session_id=session_id,
        owner_id=owner_id,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        storage_path=storage_path,
        size_bytes=len(file_bytes),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return AttachmentOut.model_validate(attachment)


from app.schemas import MessageOut, GapReport


def _session_to_out(session: Session, db: DBSession) -> SessionOut:
    """Convert a session ORM object to the API response model with complete hydration."""
    current_prompt = None
    if session.current_prompt:
        current_prompt = CasePromptOut.model_validate(session.current_prompt)
    service = SessionService(db)
    pending_turn = None
    if session.processing_turn_id:
        processing = db.get(TurnIdempotency, session.processing_turn_id)
        if processing and processing.session_id == session.id and processing.state != "complete":
            pending_turn = processing.request_payload
    return SessionOut(
        id=session.id,
        concept_id=session.concept_id,
        concept_title=session.concept.title if session.concept else "Concept Check",
        concept_slug=session.concept.slug if session.concept else "",
        stage=session.stage,
        version=session.version,
        current_prompt=current_prompt,
        diagnostic_index=session.diagnostic_index,
        diagnostic_total=len(session.baseline_prompt_ids or []) or db.query(CasePrompt).filter_by(
            concept_id=session.concept_id, stage="diagnostic", case_type="baseline", active=True,
        ).filter(CasePrompt.review_status != "rejected").count(),
        processing_status=session.processing_status,
        pending_turn=pending_turn,
        practice_active=bool(session.current_prompt and session.current_prompt.case_type in ("practice", "guided_practice")),
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[MessageOut.model_validate(m) for m in session.messages],
        attempts=service.get_attempt_reports(session),
        allowed_actions=service.get_allowed_actions(session.stage),
        evidence_cards=service.get_evidence_cards(session),
        gaps=[
            GapReport(
                id=g.id,
                description=g.description,
                evidence_quote=g.evidence_quote,
                probe_text=g.probe_text,
                status=g.status,
                source_attempt_id=g.source_attempt_id,
            )
            for g in session.gaps
        ],
    )
