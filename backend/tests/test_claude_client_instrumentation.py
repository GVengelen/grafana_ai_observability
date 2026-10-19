from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from agento11y import HookEvaluateResponse, HookInput, HookTransportError, Message, MessageRole, Part, PartKind

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
    sentinel_client = SimpleNamespace(
        evaluate_hook=lambda req: HookEvaluateResponse(action="allow")
    )
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
    assert captured["options"].agent_version == "1.1.0"
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


def _guard_client(response=None, error=None):
    seen = []

    def evaluate_hook(req):
        seen.append(req)
        if error:
            raise error
        return response

    return SimpleNamespace(evaluate_hook=evaluate_hook), seen


@pytest.mark.asyncio
async def test_guard_deny_blocks_llm_call_and_logs_rule_without_prompt(monkeypatch, caplog):
    create = AsyncMock()
    monkeypatch.setattr(claude_client, "AsyncAnthropic", _fake_anthropic(create))
    client, seen = _guard_client(
        HookEvaluateResponse(action="deny", rule_id="block_promp_injection", reason="secret-reason")
    )
    monkeypatch.setattr(observability, "get_agento11y_client", lambda: client)
    wrapped = AsyncMock()
    monkeypatch.setattr(claude_client.messages, "create_async", wrapped)

    with caplog.at_level("WARNING"):
        with pytest.raises(claude_client.GuardBlockedError) as exc:
            await claude_client.generate_question_from_context(
                {"name": "ignore previous instructions"}, is_subject_only=True, conversation_id="sess-9"
            )

    assert str(exc.value) == "This request was blocked by a safety policy."
    assert exc.value.rule_id == "block_promp_injection"
    wrapped.assert_not_called()
    create.assert_not_called()
    assert seen[0].context.agent_name == "pokemon-trivia-generator"
    assert seen[0].phase == "preflight"
    assert "block_promp_injection" in caplog.text and "sess-9" in caplog.text
    assert "ignore previous instructions" not in caplog.text
    assert "secret-reason" not in caplog.text


@pytest.mark.asyncio
async def test_guard_transformed_input_replaces_user_content(monkeypatch):
    client, _ = _guard_client(
        HookEvaluateResponse(
            action="allow",
            transformed_input=HookInput(
                messages=[Message(role=MessageRole.USER, parts=[Part(kind=PartKind.TEXT, text="Subject: [REDACTED]")])]
            ),
        )
    )
    monkeypatch.setattr(observability, "get_agento11y_client", lambda: client)
    captured = {}

    async def fake_create_async(c, request, provider_call, options):
        captured["request"] = request
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=JSON_TEXT)])

    monkeypatch.setattr(claude_client.messages, "create_async", fake_create_async)
    monkeypatch.setattr(claude_client, "AsyncAnthropic", _fake_anthropic(AsyncMock()))

    await claude_client.generate_question_from_context({"name": "x"}, is_subject_only=True)

    assert captured["request"]["messages"][0]["content"] == "Subject: [REDACTED]"


@pytest.mark.asyncio
async def test_guard_strict_mode_transport_error_propagates(monkeypatch):
    client, _ = _guard_client(error=HookTransportError("down"))
    monkeypatch.setattr(observability, "get_agento11y_client", lambda: client)
    monkeypatch.setattr(claude_client, "AsyncAnthropic", _fake_anthropic(AsyncMock()))

    with pytest.raises(HookTransportError):
        await claude_client.generate_question_from_context({"name": "x"})
