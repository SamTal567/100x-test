"""Multi-clip answer provenance, using owned fictional transcripts only."""
import hashlib
import json

import pytest
from pydantic import ValidationError

from test_learning_loop import loop
from app.db.models import Attempt, Message, Transcription, TurnIdempotency
from app.schemas import TurnRequest


def clips(db, session):
    records = [Transcription(session_id=session.id, owner_id=session.owner_id, raw_transcript=text, status="transcribed")
        for text in ("Memory is temporary", "A saved file survives")]
    db.add_all(records)
    db.commit()
    return records


def voice_request(session, records):
    return TurnRequest(client_turn_id="multi-clip", expected_version=session.version,
        prompt_id=session.current_prompt_id, action="submit_answer", input_mode="voice",
        text="Typed introduction.\n\nMemory is temporary.\n\nA saved file survives.",
        transcription_id=records[-1].id, transcription_segments=[
            {"transcription_id": record.id, "confirmed_text": record.raw_transcript + ".", "confirmation_scope": "clip"}
            for record in records])


@pytest.mark.asyncio
async def test_appended_clips_keep_their_own_confirmation_and_combined_answer(loop):
    db, _, service, session, _, _, _, _ = loop
    records = clips(db, session)
    request = voice_request(session, records)
    await service.process_turn(session, request, session.owner_id)
    assert [r.confirmed_text for r in records] == ["Memory is temporary.", "A saved file survives."]
    assert all(r.status == "confirmed" for r in records)
    attempt = db.query(Attempt).filter_by(session_id=session.id).one()
    assert attempt.answer_text == request.text
    assert attempt.raw_transcript == "Memory is temporary\n\nA saved file survives"
    for record in records:
        event = record.correction_metadata["confirmations"][0]
        assert event["transcription_ids"] == [r.id for r in records]
        assert event["attempt_id"] == attempt.id
        assert event["confirmation_scope"] == "clip"
        assert event["confirmed_text"] == record.confirmed_text
    await service.process_turn(session, request, session.owner_id)
    assert db.query(Attempt).filter_by(session_id=session.id).count() == 1
    assert all(len(r.correction_metadata["confirmations"]) == 1 for r in records)


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["foreign_owner", "foreign_session", "failed"])
async def test_every_clip_is_validated_before_saving_an_answer(loop, invalid):
    db, _, service, session, _, _, _, _ = loop
    records = clips(db, session)
    if invalid == "foreign_owner":
        records[0].owner_id = "someone-else"
    elif invalid == "foreign_session":
        records[0].session_id = "another-session"
    else:
        records[0].status = "failed"
    db.commit()
    with pytest.raises(ValueError, match="Transcription"):
        await service.process_turn(session, voice_request(session, records), session.owner_id)
    assert db.query(Attempt).filter_by(session_id=session.id).count() == 0
    assert db.query(Message).filter_by(session_id=session.id, role="learner").count() == 0
    assert records[1].status == "transcribed"


@pytest.mark.parametrize("kind", ["duplicate", "wrong_last_id", "typed_with_clips", "empty_clip"])
def test_malformed_clip_lists_are_rejected(kind):
    payload = dict(client_turn_id="invalid", expected_version=1, action="submit_answer", text="Answer",
        input_mode="voice", transcription_id="clip-2", transcription_segments=[
            {"transcription_id": "clip-1", "confirmed_text": "First"},
            {"transcription_id": "clip-2", "confirmed_text": "Second"}])
    if kind == "duplicate":
        payload["transcription_segments"][0]["transcription_id"] = "clip-2"
    elif kind == "wrong_last_id":
        payload["transcription_id"] = "unlisted"
    elif kind == "typed_with_clips":
        payload["input_mode"] = "typed"
    else:
        payload["transcription_segments"][0]["confirmed_text"] = "   "
    with pytest.raises(ValidationError):
        TurnRequest(**payload)


@pytest.mark.asyncio
async def test_existing_single_clip_clients_still_confirm_and_submit(loop):
    db, _, service, session, _, _, _, _ = loop
    record = clips(db, session)[0]
    request = TurnRequest(client_turn_id="legacy-voice", expected_version=session.version,
        action="submit_answer", text="Edited legacy answer", input_mode="voice", transcription_id=record.id)
    await service.process_turn(session, request, session.owner_id)
    assert record.confirmed_text == "Edited legacy answer" and record.status == "confirmed"
    assert db.query(Attempt).filter_by(session_id=session.id).one().raw_transcript == record.raw_transcript


@pytest.mark.asyncio
async def test_voice_clarification_is_not_attached_to_an_earlier_answer(loop):
    db, _, _, session, send, _, _, _ = loop
    await send()
    record = clips(db, session)[0]
    await send(action="clarify", text="Did the save finish?", input_mode="voice", transcription_id=record.id,
        transcription_segments=[{"transcription_id": record.id, "confirmed_text": "Did the save finish?"}])
    event = record.correction_metadata["confirmations"][0]
    assert event["attempt_id"] is None
    assert db.get(Message, event["message_id"]).content == "Did the save finish?"
    assert db.query(Attempt).filter_by(session_id=session.id).count() == 1


@pytest.mark.asyncio
async def test_legacy_saved_turn_hash_is_compatible_with_an_empty_segment_list(loop):
    db, _, service, session, _, _, _, _ = loop
    request = TurnRequest(client_turn_id="old-pending", expected_version=session.version,
        action="clarify", text="Did the save finish?")
    body = request.model_dump(mode="json")
    body.pop("transcription_segments", None)
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    key = hashlib.sha256(f"{session.id}:{request.client_turn_id}".encode()).hexdigest()
    response = service._response(session)
    db.add(TurnIdempotency(client_turn_id=key, session_id=session.id, request_body_hash=digest,
        request_payload=body, state="complete", response_snapshot=response.model_dump(mode="json")))
    db.commit()
    replay = await service.process_turn(session, request, session.owner_id)
    assert replay.version == response.version
    assert db.query(Message).filter_by(session_id=session.id).count() == 0
