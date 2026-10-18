"""SQLAlchemy ORM models for Concept Check.

Key relationships:
- gap.source_attempt_id → original attempt
- retry attempt.gap_id → gap
- assessment.attempt_id → attempt
- attempt → case prompt and rubric version
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime,
    ForeignKey, JSON, Index, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Catalogue ────────────────────────────────────────────────────

class Concept(Base):
    __tablename__ = "concepts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    module = Column(String(1), nullable=False)  # A, B, C
    slug = Column(String(100), unique=True, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    enabled = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    case_prompts = relationship("CasePrompt", back_populates="concept")
    sessions = relationship("Session", back_populates="concept")


class CasePrompt(Base):
    __tablename__ = "case_prompts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    concept_id = Column(String(36), ForeignKey("concepts.id"), nullable=False)
    authored_id = Column(String(100), nullable=True, index=True)
    active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    stage = Column(String(20), nullable=False)  # diagnostic, apply
    case_type = Column(String(20), default="baseline")  # baseline, transfer, confirmation
    scenario_text = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    source = Column(String(100), default="ai-authored")  # ai-authored, human-authored
    review_status = Column(String(20), default="unreviewed")  # unreviewed, reviewed, rejected
    created_at = Column(DateTime, default=utcnow, nullable=False)

    concept = relationship("Concept", back_populates="case_prompts")
    rubric = relationship("Rubric", back_populates="case_prompt", uselist=False)
    attempts = relationship("Attempt", back_populates="case_prompt")
    response_format = Column(String(30), default="written")  # written, diagram_repair, diagram_trace, diagram_completion, cloze
    assumptions = Column(JSON, nullable=True)
    diagram_preset = Column(JSON, nullable=True)
    cloze_preset = Column(JSON, nullable=True)


class Rubric(Base):
    """Private reference answer and rubric — never sent to the client."""
    __tablename__ = "rubrics"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_prompt_id = Column(String(36), ForeignKey("case_prompts.id"), unique=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    reference_answer = Column(Text, nullable=False)
    criteria = Column(JSON, nullable=False)  # List of {criterion, description, weight}
    created_at = Column(DateTime, default=utcnow, nullable=False)

    case_prompt = relationship("CasePrompt", back_populates="rubric")


# ── Sessions ─────────────────────────────────────────────────────

class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    owner_id = Column(String(36), nullable=False, index=True)
    concept_id = Column(String(36), ForeignKey("concepts.id"), nullable=False)
    stage = Column(String(20), default="diagnostic", nullable=False)
    version = Column(Integer, default=1, nullable=False)
    current_prompt_id = Column(String(36), ForeignKey("case_prompts.id"), nullable=True)
    diagnostic_index = Column(Integer, default=0, nullable=False)
    baseline_prompt_ids = Column(JSON, nullable=True)
    baseline_analysis_status = Column(String(20), default="pending", nullable=False)
    processing_turn_id = Column(String(100), nullable=True)
    processing_status = Column(String(20), default="idle", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    concept = relationship("Concept", back_populates="sessions")
    current_prompt = relationship("CasePrompt", foreign_keys=[current_prompt_id])
    messages = relationship("Message", back_populates="session", order_by="Message.created_at")
    attempts = relationship("Attempt", back_populates="session", order_by="Attempt.created_at")
    gaps = relationship("Gap", back_populates="session")
    interventions = relationship("Intervention", back_populates="session")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # learner, tutor, system
    content = Column(Text, nullable=False)
    stage = Column(String(20), nullable=False)
    input_mode = Column(String(20), nullable=True)  # typed, voice
    transcription_id = Column(String(36), ForeignKey("transcriptions.id"), nullable=True)
    attachment_ids = Column(JSON, nullable=True)
    provider_status = Column(String(30), default="complete", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    session = relationship("Session", back_populates="messages")
    transcription = relationship("Transcription", foreign_keys=[transcription_id])


# ── Attempts & Assessment ────────────────────────────────────────

class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    case_prompt_id = Column(String(36), ForeignKey("case_prompts.id"), nullable=False)
    rubric_version = Column(Integer, nullable=True)
    stage = Column(String(20), nullable=False)
    answer_text = Column(Text, nullable=False)
    input_mode = Column(String(20), default="typed")
    gap_id = Column(String(36), ForeignKey("gaps.id"), nullable=True)  # For retries
    raw_transcript = Column(Text, nullable=True)
    diagram_state = Column(JSON, nullable=True)
    cloze_state = Column(JSON, nullable=True)
    skill_id = Column(String(50), nullable=True)
    case_snapshot = Column(JSON, nullable=True)
    support_level = Column(String(50), default="independent", nullable=False)
    processing_status = Column(String(20), default="complete", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    session = relationship("Session", back_populates="attempts")
    case_prompt = relationship("CasePrompt", back_populates="attempts")
    gap = relationship("Gap", foreign_keys=[gap_id], back_populates="retries")
    criterion_assessments = relationship("CriterionAssessment", back_populates="attempt")


class Gap(Base):
    __tablename__ = "gaps"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    source_attempt_id = Column(String(36), ForeignKey("attempts.id"), nullable=False)
    description = Column(Text, nullable=False)
    evidence_quote = Column(Text, nullable=True)  # Quoted from learner answer
    probe_text = Column(Text, nullable=True)  # Follow-up question
    status = Column(String(20), default="identified")  # identified, probed, resolved, unresolved
    created_at = Column(DateTime, default=utcnow, nullable=False)

    session = relationship("Session", back_populates="gaps")
    source_attempt = relationship("Attempt", foreign_keys=[source_attempt_id])
    retries = relationship("Attempt", foreign_keys=[Attempt.gap_id], back_populates="gap")


class CriterionAssessment(Base):
    __tablename__ = "criterion_assessments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    attempt_id = Column(String(36), ForeignKey("attempts.id"), nullable=False)
    criterion = Column(String(200), nullable=False)
    skill_id = Column(String(50), nullable=True)
    status = Column(String(20), default="provisional")  # provisional, reviewed, corrected
    rating = Column(String(40), default="ambiguous_needs_clarification")
    met = Column(Boolean, nullable=True)  # None = unclear
    evidence = Column(Text, nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

    attempt = relationship("Attempt", back_populates="criterion_assessments")


class AssessmentReviewRevision(Base):
    """Append-only review events; the proposal remains available after corrections."""
    __tablename__ = "assessment_review_revisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    assessment_id = Column(String(36), ForeignKey("criterion_assessments.id"), nullable=False, index=True)
    reviewer_name = Column(String(100), nullable=False)
    proposal_snapshot = Column(JSON, nullable=False)
    previous_snapshot = Column(JSON, nullable=False)
    review_snapshot = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class CaseReviewRevision(Base):
    """Review metadata lives separately from immutable case/rubric versions."""
    __tablename__ = "case_review_revisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_case_id = Column(String(36), ForeignKey("case_prompts.id"), nullable=False, index=True)
    reviewed_case_id = Column(String(36), ForeignKey("case_prompts.id"), nullable=False)
    reviewer_name = Column(String(100), nullable=False)
    review_status = Column(String(20), nullable=False)
    reviewer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


# ── Interventions ────────────────────────────────────────────────

class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    intervention_type = Column(String(30), nullable=False)  # resource, cloze, exercise, explanation
    gap_id = Column(String(36), ForeignKey("gaps.id"), nullable=True)
    status = Column(String(30), default="delivered", nullable=False)
    title = Column(String(200), nullable=True)
    content = Column(Text, nullable=True)
    url = Column(String(500), nullable=True)
    opened_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    session = relationship("Session", back_populates="interventions")


# ── Attachments & Transcriptions ─────────────────────────────────

class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    owner_id = Column(String(36), nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    storage_path = Column(String(500), nullable=False)  # Local path or storage key
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class Transcription(Base):
    __tablename__ = "transcriptions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    owner_id = Column(String(36), nullable=False)
    raw_transcript = Column(Text, nullable=True)
    confirmed_text = Column(Text, nullable=True)
    input_mode = Column(String(20), default="voice")
    audio_duration_ms = Column(Integer, nullable=True)
    correction_metadata = Column(JSON, nullable=True)
    status = Column(String(20), default="pending")  # pending, transcribed, confirmed, failed
    created_at = Column(DateTime, default=utcnow, nullable=False)


# ── Idempotency ──────────────────────────────────────────────────

class TurnIdempotency(Base):
    __tablename__ = "turn_idempotency"

    client_turn_id = Column(String(100), primary_key=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    request_body_hash = Column(String(64), nullable=True)
    response_snapshot = Column(JSON, nullable=True)
    request_payload = Column(JSON, nullable=True)
    state = Column(String(20), default="complete", nullable=False)
    attempt_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_turn_idempotency_session", "session_id"),
    )
