"""Tests for Sigil generation instrumentation in claude_client.py."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_anthropic_response(text: str = '{"prompt":"Q?","answer":"A","explanation":"E"}'):
    """Return a minimal object that looks like an Anthropic Message."""
    block = types.SimpleNamespace(type="text", text=text)
    return types.SimpleNamespace(content=[block])


def _make_sigil_client():
    """Return a mock Sigil Client."""
    return MagicMock()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_instrumented_path_calls_sigil_wrapper():
    """When observability.sigil_client is set, messages.create_async is used."""
    fake_response = _make_anthropic_response()
    fake_sigil_client = _make_sigil_client()

    with (
        patch("app.core.observability.sigil_client", fake_sigil_client),
        patch("app.core.config.settings") as mock_settings,
        patch("app.services.claude_client.AsyncAnthropic") as MockAnthropic,
        patch("sigil_sdk_anthropic.messages") as mock_sigil_messages,
    ):
        mock_settings.anthropic_api_key = "sk-test"
        mock_settings.anthropic_model = "claude-haiku-4-5-20251001"
        mock_settings.anthropic_timeout_seconds = 20

        mock_sigil_messages.create_async = AsyncMock(return_value=fake_response)

        # Reload module so it picks up the patched settings
        import importlib
        import app.services.claude_client as cc
        importlib.reload(cc)

        result = await cc.generate_question_from_context(
            {"name": "pikachu", "types": ["electric"]},
            conversation_id="session-abc",
        )

    assert result == {"prompt": "Q?", "answer": "A", "explanation": "E"}
    mock_sigil_messages.create_async.assert_awaited_once()
    call_kwargs = mock_sigil_messages.create_async.call_args

    # First positional arg is the sigil client
    assert call_kwargs.args[0] is fake_sigil_client

    # Fourth positional arg is AnthropicOptions
    options = call_kwargs.args[3]
    assert options.conversation_id == "session-abc"
    assert options.agent_name == "pokemon-qa"
    assert options.tags.get("pokemon_name") == "pikachu"


@pytest.mark.asyncio
async def test_no_op_when_sigil_disabled():
    """When observability.sigil_client is None, raw Anthropic call is used."""
    fake_response = _make_anthropic_response()

    with (
        patch("app.core.observability.sigil_client", None),
        patch("app.core.config.settings") as mock_settings,
        patch("app.services.claude_client.AsyncAnthropic") as MockAnthropic,
    ):
        mock_settings.anthropic_api_key = "sk-test"
        mock_settings.anthropic_model = "claude-haiku-4-5-20251001"
        mock_settings.anthropic_timeout_seconds = 20

        mock_instance = MockAnthropic.return_value
        mock_instance.messages.create = AsyncMock(return_value=fake_response)

        import importlib
        import app.services.claude_client as cc
        importlib.reload(cc)

        result = await cc.generate_question_from_context(
            {"name": "bulbasaur", "types": ["grass"]},
            conversation_id="session-xyz",
        )

    assert result == {"prompt": "Q?", "answer": "A", "explanation": "E"}
    mock_instance.messages.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_error_propagates():
    """A provider-side exception is re-raised unchanged regardless of Sigil being enabled."""
    fake_sigil_client = _make_sigil_client()

    with (
        patch("app.core.observability.sigil_client", fake_sigil_client),
        patch("app.core.config.settings") as mock_settings,
        patch("app.services.claude_client.AsyncAnthropic"),
        patch("sigil_sdk_anthropic.messages") as mock_sigil_messages,
    ):
        mock_settings.anthropic_api_key = "sk-test"
        mock_settings.anthropic_model = "claude-haiku-4-5-20251001"
        mock_settings.anthropic_timeout_seconds = 20

        mock_sigil_messages.create_async = AsyncMock(
            side_effect=RuntimeError("upstream timeout")
        )

        import importlib
        import app.services.claude_client as cc
        importlib.reload(cc)

        with pytest.raises(RuntimeError, match="upstream timeout"):
            await cc.generate_question_from_context({"name": "mewtwo"})


@pytest.mark.asyncio
async def test_missing_api_key_raises_before_any_call():
    """RuntimeError raised early when ANTHROPIC_API_KEY is not set."""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.anthropic_api_key = ""

        import importlib
        import app.services.claude_client as cc
        importlib.reload(cc)

        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            await cc.generate_question_from_context({"name": "squirtle"})
