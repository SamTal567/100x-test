"""Dictation cleanup preserves the provider original and the learner's words."""
from io import BytesIO

import httpx
import pytest
from starlette.datastructures import UploadFile

from test_learning_loop import loop
from app.adapters import fish_audio_adapter
from app.config import Settings
from app.db.models import Transcription
from app.routers import sessions


@pytest.mark.parametrize(("raw", "expected"), [
    ("The write [pause] failed.", "The write failed."),
    ("{pause} The record survives (long pause).", "The record survives."),
    ("[Woman speaking] Read the saved record. [women speaking]", "Read the saved record."),
    ("<|speaker:0|>Read<|speaker:1|>then render.", "Read then render."),
    ("[female voice] Store it.\n\n[man speaking] Fetch it.", "Store it.\n\nFetch it."),
    ("[pause] {pause} (pause)", ""),
    ('Read items[pause], JSON {"pause": true}, [GET /books] and [12:30].',
     'Read items[pause], JSON {"pause": true}, [GET /books] and [12:30].'),
    ('Keep `[pause]` and ```text\n[pause]\n``` as code.',
     'Keep `[pause]` and ```text\n[pause]\n``` as code.'),
    ('The words woman speaking and pause are meaningful. "[pause]" is a label.',
     'The words woman speaking and pause are meaningful. "[pause]" is a label.'),
    ("The database [unknown annotation] keeps नमस्ते at 12:30.",
     "The database [unknown annotation] keeps नमस्ते at 12:30."),
])
def test_cleanup_is_narrow_and_preserves_reasoning(raw, expected):
    from app.transcript_text import clean_transcript
    assert clean_transcript(raw) == expected
    assert clean_transcript(expected) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["transcribe-1-pro", "transcribe-1"])
async def test_adapter_disables_supported_event_tags_and_retains_raw(monkeypatch, model):
    raw = "<|speaker:0|>The record [pause] persists."
    def handle(request):
        assert request.headers["model"] == model
        assert b'name="ignore_timestamps"\r\n\r\ntrue' in request.content
        assert (b'name="tag_audio_events"\r\n\r\nfalse' in request.content) == (model == "transcribe-1-pro")
        return httpx.Response(200, json={"text": raw, "duration": 2})
    original_client = httpx.AsyncClient
    monkeypatch.setattr(fish_audio_adapter.httpx, "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    adapter = fish_audio_adapter.FishAudioAdapter()
    adapter.settings = Settings(fish_audio_api_key="fictional-test", fish_audio_model=model, _env_file=None)
    result = await adapter.transcribe(b"fictional audio", "test.webm", "audio/webm")
    assert result["success"] is True
    assert result["raw_transcript"] == raw
    assert result["transcript"] == "The record persists."


@pytest.mark.asyncio
async def test_upload_preserves_provider_original_but_returns_editable_suggestion(loop, monkeypatch):
    db, _, _, session, _, _, _, _ = loop
    raw = "<|speaker:0|>The record [pause] persists."
    class Provider:
        async def transcribe(self, **kwargs):
            return {"success": True, "raw_transcript": raw, "transcript": "The record persists.", "duration_ms": 2000}
    monkeypatch.setattr(sessions, "get_fish_audio_adapter", Provider)
    result = await sessions.upload_transcription(session.id,
        UploadFile(BytesIO(b"fictional audio"), filename="test.webm"), session.owner_id, db)
    saved = db.get(Transcription, result.id)
    assert saved.raw_transcript == raw
    assert saved.confirmed_text is None
    assert result.raw_transcript == raw
    assert result.cleaned_transcript == "The record persists."
    assert saved.status == "transcribed"
