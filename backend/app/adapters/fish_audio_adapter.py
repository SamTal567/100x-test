"""Fish Audio speech-to-text adapter.

POST https://api.fish.audio/v1/asr with multipart audio.
Model: transcribe-1-pro (configurable).
Returns transcript only — no assessment.

When FISH_AUDIO_API_KEY is not set, returns explicit unavailable state.
"""

from __future__ import annotations
from typing import Optional
import logging

import httpx

from app.config import get_settings
from app.transcript_text import clean_transcript

logger = logging.getLogger(__name__)

FISH_AUDIO_ASR_URL = "https://api.fish.audio/v1/asr"


class FishAudioAdapter:
    def __init__(self):
        self.settings = get_settings()

    @property
    def available(self) -> bool:
        return self.settings.fish_audio_available

    async def transcribe(self, audio_bytes: bytes, filename: str, content_type: str) -> dict:
        """Transcribe audio using Fish Audio ASR.

        Returns:
            dict with keys: success, transcript, duration_ms, error
        """
        if not self.available:
            return {
                "success": False,
                "transcript": None,
                "duration_ms": None,
                "error": "Fish Audio API key not configured. Speech input unavailable.",
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {
                    "audio": (filename, audio_bytes, content_type),
                }
                headers = {
                    "Authorization": f"Bearer {self.settings.fish_audio_api_key}",
                    "model": self.settings.fish_audio_model,
                }
                data = {
                    "language": "en",
                    "ignore_timestamps": "true",
                }
                if self.settings.fish_audio_model == "transcribe-1-pro":
                    data["tag_audio_events"] = "false"

                response = await client.post(
                    FISH_AUDIO_ASR_URL,
                    files=files,
                    data=data,
                    headers=headers,
                )

                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"Fish Audio ASR error {response.status_code}: {error_text}")
                    return {
                        "success": False,
                        "transcript": None,
                        "duration_ms": None,
                        "error": f"Transcription failed (HTTP {response.status_code})",
                    }

                result = response.json()
                raw_text = result.get("text", "")
                cleaned_transcript = clean_transcript(raw_text)
                duration = result.get("duration", None)

                return {
                    "success": True,
                    "transcript": cleaned_transcript,
                    "raw_transcript": raw_text,
                    "duration_ms": int(duration * 1000) if duration else None,
                    "error": None,
                }

        except httpx.TimeoutException:
            logger.error("Fish Audio ASR timed out")
            return {
                "success": False,
                "transcript": None,
                "duration_ms": None,
                "error": "Transcription timed out",
            }
        except Exception as e:
            logger.error(f"Fish Audio ASR error: {e}")
            return {
                "success": False,
                "transcript": None,
                "duration_ms": None,
                "error": f"Transcription failed: {type(e).__name__}",
            }


# Singleton
_adapter: Optional[FishAudioAdapter] = None


def get_fish_audio_adapter() -> FishAudioAdapter:
    global _adapter
    if _adapter is None:
        _adapter = FishAudioAdapter()
    return _adapter
