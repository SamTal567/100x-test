"""Concept Check backend configuration.

This module manages environment variables, application settings, and provider
availability flags. It uses Pydantic Settings for type-safe configuration loading
and functools.lru_cache to implement a cached singleton pattern.
"""

from functools import lru_cache
import secrets
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and local .env file.
    
    Order of precedence:
      1. Actual OS environment variables (e.g., from Docker, export, or cloud provider)
      2. Key-value pairs defined in the local `.env` file
      3. Class attribute defaults defined below
    """

    # ── Database Configuration ───────────────────────────────────────────
    # Connection string for SQLAlchemy ORM.
    # Default: local SQLite file (concept_check.db).
    # To switch to Supabase/PostgreSQL: set DATABASE_URL=postgresql://user:pass@host:5432/db
    database_url: str = "sqlite:///./concept_check.db"

    # ── Security & Authentication ─────────────────────────────────────────
    # Cryptographic secret key used by itsdangerous to sign session cookies (cc_session).
    # Prevents client-side tampering of anonymous user IDs.
    environment: str = "development"
    secret_key: str = ""
    # Secret key required to access reviewer APIs (/v1/review/assessments)
    reviewer_api_key: str = ""

    @model_validator(mode="after")
    def secure_signing_configuration(self):
        if self.reviewer_api_key.strip() == "concept-check-reviewer-secret":
            # A formerly shipped public credential must not survive stale .env files.
            self.reviewer_api_key = ""
        unsafe = not self.secret_key.strip() or self.secret_key in {
            "change-me-in-production", "concept-check-reviewer-secret",
        }
        if self.environment.lower() in {"production", "prod"}:
            if unsafe or len(self.secret_key) < 32:
                raise ValueError("Production requires an explicit SECRET_KEY of at least 32 characters.")
        elif unsafe:
            # Cached get_settings keeps one local key for this process only.
            # Configure SECRET_KEY explicitly to preserve anonymous sessions on restart.
            self.secret_key = secrets.token_urlsafe(48)
        return self

    # ── CORS (Cross-Origin Resource Sharing) ──────────────────────────────
    # Comma-separated list of allowed frontend origins (e.g. Vite dev server).
    cors_origins: str = "http://localhost:5173"

    # ── OpenAI Integration ────────────────────────────────────────────────
    # API key for OpenAI LLM services. If empty, the adapter gracefully falls back to a stub.
    openai_api_key: str = ""
    # Model ID to invoke for gap analysis, follow-up probes, and rubrics assessment.
    openai_model: str = "gpt-6-luna"

    # ── Fish Audio Integration ────────────────────────────────────────────
    # API key for Fish Audio Speech-to-Text (ASR). If empty, falls back to a stub.
    fish_audio_api_key: str = ""
    # Recommended model for high-accuracy long-form speech recognition with speaker diarization.
    fish_audio_model: str = "transcribe-1-pro"

    # ── Pydantic Model Configuration ──────────────────────────────────────
    model_config = {
        # Path to local environment file to read from if present
        "env_file": ".env",
        # Character encoding for reading .env file
        "env_file_encoding": "utf-8",
    }

    # ── Dynamic Computed Properties (Getters) ─────────────────────────────

    @property
    def openai_available(self) -> bool:
        """Returns True if an OpenAI API key is configured and non-empty."""
        return bool(self.openai_api_key)

    @property
    def fish_audio_available(self) -> bool:
        """Returns True if a Fish Audio API key is configured and non-empty."""
        return bool(self.fish_audio_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        """Parses the comma-separated cors_origins string into a clean list of origins.
        
        Example:
            'http://localhost:5173, http://127.0.0.1:5173'
            -> ['http://localhost:5173', 'http://127.0.0.1:5173']
        """
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Provides a cached singleton instance of application settings.
    
    The @lru_cache decorator ensures Settings() is constructed only once
    during the application lifecycle, avoiding redundant disk I/O when reading .env.
    """
    return Settings()
