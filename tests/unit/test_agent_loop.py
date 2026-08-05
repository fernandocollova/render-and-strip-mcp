"""Tests for fresh browser-agent model context and bounded turn execution."""

from __future__ import annotations

import asyncio

import pytest

import render_and_strip_mcp.agent_loop as agent_loop
from render_and_strip_mcp.agent_context import BrowserActionResult, build_model_messages
from render_and_strip_mcp.config import AgentSettings, LlmSettings
from render_and_strip_mcp.errors import ExecutionLimitError
from render_and_strip_mcp.model_stream import ModelTurn, RequestedToolCall
from render_and_strip_mcp.playwright_tools import ToolCatalog


def llm_settings() -> LlmSettings:
    """Build model settings for pure agent-loop tests."""

    return LlmSettings(
        model="test-model",
        api_base="https://model.example/v1",
        api_key="test-key",
    )


def catalog() -> ToolCatalog:
    """Build a one-action model-tool mapping."""

    return ToolCatalog([], {"browser_type": "browser_type"})


def test_fresh_messages_keep_compact_context_and_omit_payload_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each model request contains only system plus current compact user state."""

    observed_messages: list[list[dict[str, str]]] = []
    turns = iter(
        [
            ModelTurn(
                content="",
                tool_call=RequestedToolCall(
                    "browser_type",
                    "call-1",
                    {"text": "secret", "target": "ref"},
                ),
                reasoning_fragments=(),
            ),
            ModelTurn(content="done", tool_call=None, reasoning_fragments=()),
        ]
    )

    async def fake_stream_model_turn(
        settings: LlmSettings,
        tools: ToolCatalog,
        messages: list[dict[str, str]],
    ) -> ModelTurn:
        observed_messages.append(messages)
        return next(turns)

    async def execute_browser_action(
        tool_name: str, arguments: dict[str, object]
    ) -> BrowserActionResult:
        assert tool_name == "browser_type"
        assert arguments == {"text": "secret", "target": "ref"}
        return BrowserActionResult("new observation", "https://example.test/next")

    monkeypatch.setattr(agent_loop, "stream_model_turn", fake_stream_model_turn)

    asyncio.run(
        agent_loop.run_agent_loop(
            llm_settings(),
            AgentSettings(),
            catalog(),
            "Complete the task",
            "https://example.test/",
            "initial observation",
            execute_browser_action,
            ['browser_navigate(url="https://example.test/") -> success'],
        )
    )

    assert [[message["role"] for message in messages] for messages in observed_messages] == [
        ["system", "user"],
        ["system", "user"],
    ]
    second_user_message = observed_messages[1][1]["content"]
    assert "secret" not in second_user_message
    assert "text=<6 chars omitted>" in second_user_message
    assert "new observation" in second_user_message
    assert '"role": "tool"' not in second_user_message


def test_context_uses_exactly_one_system_and_one_user_message() -> None:
    """No completed assistant or tool history is replayed into the next model turn."""

    messages = build_model_messages("task", [], "https://example.test/", "observation")

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_model_context_internalizes_loaded_page_cleaning_guidance() -> None:
    """Internal system guidance, not caller text, controls current-page cleaning behavior."""

    task = "Clean the current page."
    messages = build_model_messages(task, [], "https://example.test/", "observation")

    assert (
        "service has already loaded the caller's requested initial page" in (messages[0]["content"])
    )
    assert "Do not call browser tools or functions" in messages[0]["content"]
    assert "reply exactly TASK_COMPLETE without a tool call" in messages[0]["content"]
    assert "only when necessary to complete the caller's task" in messages[0]["content"]
    assert f"Task:\n{task}" in messages[1]["content"]


def test_model_turn_and_browser_action_limits_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The loop fails at both configured deterministic count boundaries."""

    tool_turn = ModelTurn(
        content="",
        tool_call=RequestedToolCall("browser_type", "call-1", {}),
        reasoning_fragments=(),
    )

    async def fake_stream_model_turn(*arguments: object) -> ModelTurn:
        return tool_turn

    async def execute_browser_action(*arguments: object) -> BrowserActionResult:
        return BrowserActionResult("observation", "https://example.test/")

    monkeypatch.setattr(agent_loop, "stream_model_turn", fake_stream_model_turn)

    with pytest.raises(ExecutionLimitError, match="Browser action"):
        asyncio.run(
            agent_loop.run_agent_loop(
                llm_settings(),
                AgentSettings(max_model_turns=2, max_browser_actions=1),
                catalog(),
                "task",
                "https://example.test/",
                "observation",
                execute_browser_action,
            )
        )

    with pytest.raises(ExecutionLimitError, match="Model-turn"):
        asyncio.run(
            agent_loop.run_agent_loop(
                llm_settings(),
                AgentSettings(max_model_turns=1, max_browser_actions=2),
                catalog(),
                "task",
                "https://example.test/",
                "observation",
                execute_browser_action,
            )
        )
