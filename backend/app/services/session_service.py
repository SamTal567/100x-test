"""Public session-service API; implementation is split into focused modules."""
from app.adapters.openai_adapter import get_openai_adapter, AssessmentResult
from app.services.learning_engine import SessionService, STAGE_ACTIONS

