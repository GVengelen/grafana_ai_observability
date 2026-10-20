from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import observability
from app.services import claude_client

JSON_TEXT = '{"prompt": "p", "answer": "a", "explanation": "e"}'


def _fake_anthropic(create: AsyncMock):
    return MagicMock(return_value=SimpleNamespace(messages=SimpleNamespace(create=create)))


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setattr(claude_client.settings, "anthropic_api_key", "test-key")


@pytest.mark.asyncio
async def test_uses_instrumented_wrapper_with_agent_identity(monkeypatch):
    create = AsyncMock()
    monkeypatch.setattr(claude_client, "AsyncAnthropic", _fake_anthropic(create))
    sentinel_client = object()
    monkeypatch.setattr(observability, "get_agento11y_client", lambda: sentinel_client)

    captured = {}

    async def fake_create_async(client, request, provider_call, options):
        captured.update(client=client, request=request, options=options)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=JSON_TEXT)])

    monkeypatch.setattr(claude_client.messages, "create_async", fake_create_async, raising=False)

    result = await claude_client.generate_question_from_context(
        {"name": "pikachu"}, conversation_id="sess-1"
    )

    assert result["answer"] == "a"
    assert captured["client"] is sentinel_client
    assert captured["options"].agent_name == "pokemon-trivia-generator"
    assert captured["options"].agent_version == "1.0.0"
    assert captured["options"].conversation_id == "sess-1"
    assert captured["options"].raw_artifacts is False
    create.assert_not_called()


@pytest.mark.asyncio
async def test_falls_back_to_plain_call_without_client(monkeypatch):
    create = AsyncMock(
        return_value=SimpleNamespace(content=[SimpleNamespace(type="text", text=JSON_TEXT)])
    )
    monkeypatch.setattr(claude_client, "AsyncAnthropic", _fake_anthropic(create))
    monkeypatch.setattr(observability, "get_agento11y_client", lambda: None)

    result = await claude_client.generate_question_from_context({"name": "pikachu"})

    assert result["prompt"] == "p"
    create.assert_awaited_once()
