"""Pydantic schemas for API request/response validation."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


AssessmentRating = Literal[
    "demonstrated", "partially_demonstrated", "not_addressed",
    "ambiguous_needs_clarification", "technical_failure",
]


def sanitize_public_snapshot(value):
    """Copy authored exercise data while dropping private answer keys at every depth."""
    if isinstance(value, dict):
        return {
            key: sanitize_public_snapshot(item)
            for key, item in value.items()
            if not (str(key).casefold().startswith(("correct", "private", "_"))
                    or str(key).casefold() in {
                        "answer_key", "reference_answer", "rubric", "criteria",
                        "assessment_guidance", "acceptable_alternatives",
                    })
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_public_snapshot(item) for item in value]
    return value


# ── Concepts ─────────────────────────────────────────────────────

class ConceptOut(BaseModel):
    id: str
    module: str
    slug: str
    title: str
    description: str
    enabled: bool

    model_config = {"from_attributes": True}


# ── Sessions ─────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    concept_id: str = Field(min_length=1, max_length=100)


class CasePromptOut(BaseModel):
    id: str
    stage: str
    case_type: str
    scenario_text: str
    response_format: str = "written"
    assumptions: Optional[list[str]] = None
    diagram_preset: Optional[dict] = None
    cloze_preset: Optional[dict] = None
    question_parts: Optional[list[dict]] = None
    version: int = 1
    review_status: str = "unreviewed"

    @field_validator("diagram_preset", "cloze_preset", "question_parts", mode="before")
    @classmethod
    def remove_private_exercise_keys(cls, value):
        return sanitize_public_snapshot(value)

    model_config = {"from_attributes": True}


class SessionListItem(BaseModel):
    id: str
    concept_id: str
    concept_title: str = ""
    stage: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Messages ─────────────────────────────────────────────────────

class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    stage: str
    input_mode: Optional[str] = None
    created_at: datetime
    provider_status: str = "complete"

    model_config = {"from_attributes": True}


# ── Turns ────────────────────────────────────────────────────────

class TranscriptionSegment(BaseModel):
    transcription_id: str = Field(min_length=1, max_length=100)
    confirmed_text: str = Field(min_length=1, max_length=30000)
    confirmation_scope: Literal["clip", "legacy_draft"] = "clip"

    @field_validator("confirmed_text")
    @classmethod
    def nonempty_clip(cls, value):
        if not value.strip():
            raise ValueError("A reviewed transcript cannot be empty")
        return value


class TurnRequest(BaseModel):
    client_turn_id: str = Field(min_length=1, max_length=100)
    expected_version: int = Field(ge=1, le=2147483647)
    prompt_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    action: Literal[
        "submit_answer", "clarify", "correct_ai", "answer_probe",
        "request_hint", "request_teaching", "request_practice",
        "request_help", "resource_opened", "resource_completed", "continue",
        "submit_practice", "finish_session", "retry_processing"
    ]
    text: Optional[str] = Field(default=None, max_length=30000)
    diagram_state: Optional[dict] = None
    cloze_state: Optional[dict] = None
    attachment_ids: list[str] = Field(default_factory=list, max_length=8)
    transcription_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    transcription_segments: list[TranscriptionSegment] = Field(default_factory=list, max_length=20)
    resource_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    input_mode: Optional[Literal["typed", "voice"]] = "typed"

    @model_validator(mode="after")
    def validate_transcription_segments(self):
        if self.transcription_segments:
            ids = [segment.transcription_id for segment in self.transcription_segments]
            if self.input_mode != "voice":
                raise ValueError("Transcript clips require voice input mode")
            if len(set(ids)) != len(ids):
                raise ValueError("Each transcription can appear only once")
            if self.transcription_id and self.transcription_id != ids[-1]:
                raise ValueError("The primary transcription must match the last clip")
        return self


class TurnResponse(BaseModel):
    stage: str
    version: int
    messages: list[MessageOut]
    current_prompt: Optional[CasePromptOut] = None
    allowed_actions: list[str]
    processing_status: str = "complete"
    diagnostic_index: int = 0
    diagnostic_total: int = 0
    practice_active: bool = False
    evidence_cards: list[dict] = Field(default_factory=list)
    intervention: Optional[dict] = None


# ── Reports ──────────────────────────────────────────────────────

class GapReport(BaseModel):
    id: str
    description: str
    evidence_quote: Optional[str] = None
    probe_text: Optional[str] = None
    status: str
    source_attempt_id: Optional[str] = None
    addressed_by_attempt_id: Optional[str] = None
    addressed_stage: Optional[str] = None


class CriterionDetail(BaseModel):
    criterion: str
    skill_id: Optional[str] = None
    rating: Optional[str] = None
    met: Optional[bool] = None
    evidence: Optional[str] = None
    reviewer_notes: Optional[str] = None
    status: str = "provisional"
    unprompted: Optional[bool] = None
    unprompted_note: Optional[str] = None
    question_part_id: Optional[str] = None
    coverage: Optional[str] = None
    issue_type: Optional[str] = None
    demonstrated_explanation: Optional[str] = None
    explanation: Optional[str] = None
    next_action: Optional[str] = None


class AttemptReport(BaseModel):
    id: str
    stage: str
    case_type: str
    scenario_text: str
    answer_text: str
    response_format: str = "written"
    diagram_state: Optional[dict] = None
    cloze_state: Optional[dict] = None
    criteria: list[dict] = Field(default_factory=list)
    question_parts: Optional[list[dict]] = None
    question_parts_coverage: Optional[list[dict]] = None
    support_level: str = "independent"
    case_prompt_id: Optional[str] = None
    case_version: Optional[int] = None
    provenance_warning: Optional[str] = None
    rubric_version: Optional[int] = None
    diagram_preset: Optional[dict] = None
    cloze_preset: Optional[dict] = None
    gap_id: Optional[str] = None
    processing_status: str = "complete"
    created_at: Optional[datetime] = None
    score: Optional[int] = None
    met_criteria_count: Optional[int] = None
    total_criteria_count: Optional[int] = None
    uncertain_criteria_count: int = 0
    unavailable_criteria_count: int = 0

    @field_validator("diagram_preset", "cloze_preset", "question_parts", mode="before")
    @classmethod
    def remove_private_exercise_keys(cls, value):
        return sanitize_public_snapshot(value)


class SessionReport(BaseModel):
    session_id: str
    concept_title: str
    stage: str
    outcome: str  # gap_found, no_gap, inconclusive, criteria_demonstrated
    gaps: list[GapReport] = Field(default_factory=list)
    attempts: list[AttemptReport] = Field(default_factory=list)
    interventions_used: list[dict] = Field(default_factory=list)
    assessment_status: str = "provisional"  # provisional, reviewed
    outcome_reason: str = ""
    skill_comparisons: list[dict] = Field(default_factory=list)
    previous_sessions: list[dict] = Field(default_factory=list)
    processing_status: str = "idle"
    initial_score: Optional[int] = None
    final_score: Optional[int] = None
    score_change: Optional[int] = None
    score_summary: Optional[str] = None
    stage_summaries: list[dict] = Field(default_factory=list)
    session_summary: Optional[dict] = None



class SessionOut(BaseModel):
    id: str
    concept_id: str
    concept_title: str = ""
    concept_slug: str = ""
    stage: str
    version: int
    current_prompt: Optional[CasePromptOut] = None
    diagnostic_index: int
    diagnostic_total: int = 0
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = Field(default_factory=list)
    attempts: list[AttemptReport] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    evidence_cards: list[dict] = Field(default_factory=list)
    gaps: list[GapReport] = Field(default_factory=list)
    processing_status: str = "idle"
    practice_active: bool = False
    pending_turn: Optional[dict] = None

    model_config = {"from_attributes": True}


# ── Transcription ────────────────────────────────────────────────

class TranscriptionOut(BaseModel):
    id: str
    raw_transcript: Optional[str] = None
    confirmed_text: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Attachments ──────────────────────────────────────────────────

class AttachmentOut(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Review ───────────────────────────────────────────────────────

class AssessmentReviewItem(BaseModel):
    id: str
    attempt_id: str
    criterion: str
    skill_id: Optional[str] = None
    rating: Optional[str] = None
    status: str
    met: Optional[bool] = None
    evidence: Optional[str] = None
    scenario_text: str = ""
    answer_text: str = ""
    diagram_state: Optional[dict] = None
    reference_answer: str = ""
    reviewer_notes: Optional[str] = None
    case_prompt_id: Optional[str] = None
    case_version: Optional[int] = None
    rubric_version: Optional[int] = None
    diagram_preset: Optional[dict] = None
    cloze_preset: Optional[dict] = None
    cloze_state: Optional[dict] = None
    proposal: Optional[dict] = None
    review_history: list[dict] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AssessmentReviewSubmit(BaseModel):
    status: Literal["reviewed", "corrected"]
    met: Optional[bool] = None
    reviewer_notes: Optional[str] = Field(default=None, max_length=5000)
    reviewer_name: str = Field(default="Authorized reviewer", min_length=1, max_length=100)
    rating: Optional[AssessmentRating] = None

    @model_validator(mode="after")
    def validate_rating_semantics(self):
        if not self.reviewer_name.strip():
            raise ValueError("Reviewer name must not be blank.")
        if self.rating is not None and "met" in self.model_fields_set:
            expected = (True if self.rating == "demonstrated" else
                        False if self.rating in {"partially_demonstrated", "not_addressed"} else None)
            if self.met is not expected:
                raise ValueError("Rating and met must describe the same judgment.")
        return self


class CaseReviewSubmit(BaseModel):
    review_status: Literal["reviewed", "rejected"]
    reviewer_name: str = Field(min_length=1, max_length=100)
    reviewer_notes: Optional[str] = Field(default=None, max_length=5000)
    scenario_text: Optional[str] = Field(default=None, min_length=1, max_length=30000)
    reference_answer: Optional[str] = Field(default=None, min_length=1, max_length=30000)
    criteria: Optional[list[dict]] = Field(default=None, min_length=1, max_length=30)
    assumptions: Optional[list[str]] = None
    diagram_preset: Optional[dict] = None
    cloze_preset: Optional[dict] = None

    @field_validator("reviewer_name")
    @classmethod
    def named_reviewer(cls, value):
        if not value.strip():
            raise ValueError("Reviewer name must not be blank.")
        return value.strip()


# ── Health ───────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    openai_available: bool = False
    fish_audio_available: bool = False


# ── User Authentication ──────────────────────────────────────────

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserRegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_REGEX.match(v):
            raise ValueError("Invalid email format")
        return v


class UserLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_REGEX.match(v):
            raise ValueError("Invalid email format")
        return v


class UserOut(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AuthStatus(BaseModel):
    authenticated: bool
    user: Optional[UserOut] = None
