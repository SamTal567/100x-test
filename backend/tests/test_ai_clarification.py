from types import SimpleNamespace

import pytest

from app.adapters.openai_adapter import OpenAIAdapter, TutorResponse
from app.config import Settings
from app.db.models import Attempt, Intervention, Message
from app.schemas import TurnRequest
from test_learning_loop import loop  # noqa: F401


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ['diagnostic', 'investigate', 'apply'])
async def test_clarification_answers_question_without_submitting_or_advancing(loop, stage):
    db, _, service, session, send, _, ai, cases = loop
    case = next(c for c in cases if c.stage == stage)
    session.stage, session.current_prompt_id = stage, case.id
    db.commit()
    calls = []

    async def clarify(**kwargs):
        calls.append(kwargs)
        return TutorResponse(message='The task asks for an explanation of the stated restart, not a definition.', action_type='clarify')

    ai.clarify_scenario = clarify
    response = await send(action='clarify', text='What output do you want?')
    assert calls[0]['question'] == 'What output do you want?'
    assert calls[0]['scenario'] == case.scenario_text
    assert set(calls[0]) == {'scenario', 'assumptions', 'question', 'stage', 'history'}
    assert response.stage == stage and response.current_prompt.id == case.id
    assert db.query(Attempt).filter_by(session_id=session.id).count() == 0
    assert response.messages[-1].content.startswith('The task asks')
    assert db.query(Message).filter_by(session_id=session.id, role='learner').one().content == 'What output do you want?'
    event = db.query(Intervention).filter_by(session_id=session.id).one()
    assert event.intervention_type == 'clarification' and event.status == 'delivered'


@pytest.mark.asyncio
async def test_clarification_history_is_case_scoped_and_replay_does_not_call_provider_twice(loop):
    db, _, service, session, send, _, ai, cases = loop
    calls = []

    async def clarify(**kwargs):
        calls.append(kwargs)
        return TutorResponse(message='Clarified: ' + kwargs['question'], action_type='clarify')

    ai.clarify_scenario = clarify
    request = TurnRequest(client_turn_id='clarify-once', expected_version=session.version,
        prompt_id=cases[0].id, action='clarify', text='What does restart mean here?')
    await service.process_turn(session, request, session.owner_id)
    await service.process_turn(session, request, session.owner_id)
    assert len(calls) == 1
    await send(action='clarify', text='Can you rephrase that?')
    assert calls[-1]['history'][0]['content'] == request.text
    assert calls[-1]['history'][1]['content'] == 'Clarified: ' + request.text
    session.current_prompt_id = cases[1].id
    db.commit()
    await send(action='clarify', text='A different case question')
    assert calls[-1]['history'] == []


@pytest.mark.asyncio
async def test_clarification_provider_failure_is_visible_and_not_successful_help(loop):
    db, _, service, session, send, _, ai, _ = loop

    async def clarify(**kwargs):
        return TutorResponse(message='AI clarification failed; your question is saved.', action_type='clarify', status='error')

    ai.clarify_scenario = clarify
    response = await send(action='clarify', text='What is being asked?')
    assert response.messages[-1].provider_status == 'error'
    event = db.query(Intervention).filter_by(session_id=session.id).one()
    assert event.status == 'error'
    assert db.query(Message).filter_by(session_id=session.id, role='learner').count() == 1


@pytest.mark.asyncio
async def test_clarification_adapter_grounding_and_provider_failure(monkeypatch):
    ai = OpenAIAdapter()
    ai.settings = Settings(openai_api_key='test-only', _env_file=None)
    captured = {}

    def complete(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Explain which facts change after the restart.'))])

    monkeypatch.setattr(ai, '_create_completion', complete)
    result = await ai.clarify_scenario('Public scenario', ['Stated fact'], 'What is being asked?', 'apply', [])
    assert result.status == 'complete'
    prompt = captured['messages'][0]['content'].lower()
    assert 'do not solve' in prompt and 'do not invent' in prompt
    assert 'no answer keys' in prompt
    data = captured['messages'][1]['content']
    assert 'Public scenario' in data and 'What is being asked?' in data and 'Stated fact' in data
    ai.settings = Settings(openai_api_key='', _env_file=None)
    assert (await ai.clarify_scenario('Scenario', [], 'Why?', 'diagnostic', [])).status == 'unavailable'
    ai.settings = Settings(openai_api_key='test-only', _env_file=None)
    monkeypatch.setattr(ai, '_create_completion', lambda **_: (_ for _ in ()).throw(RuntimeError('private-provider-detail')))
    failure = await ai.clarify_scenario('Scenario', [], 'Why?', 'diagnostic', [])
    assert failure.status == 'error' and 'private-provider-detail' not in failure.message
