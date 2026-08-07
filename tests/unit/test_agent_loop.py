"""Tests for compact stage context and bounded typed stage execution."""

from __future__ import annotations

import asyncio

import pytest

import render_and_strip_mcp.agent_loop as agent_loop
from render_and_strip_mcp.agent_context import PageState, build_stage_messages
from render_and_strip_mcp.config import AgentSettings, LlmSettings
from render_and_strip_mcp.errors import ExecutionLimitError, MissingStageCompletionError
from render_and_strip_mcp.model_stream import ModelTurn, RequestedToolCall
from render_and_strip_mcp.playwright_tools import ToolCatalog
from render_and_strip_mcp.stage_models import (
    ACCESS_COMPLETION_TOOL,
    COLLECTION_COMPLETION_TOOL,
    DISCOVERY_COMPLETION_TOOL,
    RECONSTRUCTION_COMPLETION_TOOL,
    AccessCheckpoint,
)


def llm_settings() -> LlmSettings:
    """Build model settings for pure stage-runner tests."""

    return LlmSettings(
        model="test-model",
        api_base="https://model.example/v1",
        api_key="test-key",
    )


def catalog() -> ToolCatalog:
    """Build a one-action model-tool mapping."""

    return ToolCatalog([], {"browser_type": "browser_type"})


def access_completion_turn() -> ModelTurn:
    """Return the valid local report that completes the access stage."""

    return ModelTurn(
        content="",
        tool_call=RequestedToolCall(
            "complete_access",
            "call-complete",
            {
                "target_state": "The report is visible.",
                "reconstruction_instructions": [],
                "verification": ["The report heading is visible."],
            },
            "completion",
        ),
        reasoning_fragments=(),
    )


class RecordingProgressReporter:
    """Record model-reasoning and lifecycle calls from the stage runner."""

    def __init__(self):
        self.reasoning_fragments: list[str] = []
        self.flush_count = 0

    async def accept(self, reasoning_fragment: str) -> None:
        self.reasoning_fragments.append(reasoning_fragment)

    async def flush_if_needed(self) -> None:
        self.flush_count += 1


def test_stage_runner_uses_fresh_compact_context_and_local_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remote actions update one stage's current snapshot before its local completion call."""

    observed_messages: list[list[dict[str, str]]] = []
    turns = iter(
        [
            ModelTurn(
                content="",
                tool_call=RequestedToolCall(
                    "browser_type", "call-1", {"text": "secret", "target": "ref"}
                ),
                reasoning_fragments=(),
            ),
            access_completion_turn(),
        ]
    )

    async def fake_stream_model_turn(*arguments: object) -> ModelTurn:
        observed_messages.append(arguments[2])  # type: ignore[arg-type]
        return next(turns)

    async def execute_browser_action(tool_name: str, arguments: dict[str, object]) -> PageState:
        assert tool_name == "browser_type"
        assert arguments == {"text": "secret", "target": "ref"}
        return PageState("new snapshot", "https://example.test/next")

    monkeypatch.setattr(agent_loop, "stream_model_turn", fake_stream_model_turn)

    result = asyncio.run(
        agent_loop.run_stage(
            llm_settings(),
            AgentSettings(),
            catalog(),
            ACCESS_COMPLETION_TOOL,
            "Complete the task",
            PageState("initial snapshot", "https://example.test/"),
            execute_browser_action,
        )
    )

    assert result.page_state == PageState("new snapshot", "https://example.test/next")
    assert [[message["role"] for message in messages] for messages in observed_messages] == [
        ["system", "user"],
        ["system", "user"],
    ]
    second_user_message = observed_messages[1][1]["content"]
    assert "secret" not in second_user_message
    assert "text=<6 chars omitted>" in second_user_message
    assert "new snapshot" in second_user_message
    assert '"role": "tool"' not in second_user_message


def test_stage_runner_uses_public_interval_respecting_progress_flush(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completed model turn delegates progress timing to the reporter's public API."""

    reporter = RecordingProgressReporter()

    async def fake_stream_model_turn(*arguments: object) -> ModelTurn:
        reasoning_callback = arguments[3]
        assert callable(reasoning_callback)
        await reasoning_callback("model reasoning")
        return access_completion_turn()

    async def unused_action(*arguments: object) -> PageState:
        raise AssertionError("remote action should not execute")

    monkeypatch.setattr(agent_loop, "stream_model_turn", fake_stream_model_turn)

    asyncio.run(
        agent_loop.run_stage(
            llm_settings(),
            AgentSettings(),
            catalog(),
            ACCESS_COMPLETION_TOOL,
            "task",
            PageState("snapshot", "https://example.test/"),
            unused_action,
            reporter,  # type: ignore[arg-type]
        )
    )

    assert reporter.reasoning_fragments == ["model reasoning"]
    assert reporter.flush_count == 1


def test_stage_context_exposes_only_permitted_prior_stage_inputs() -> None:
    """Stage-specific messages prevent stale reports and orchestration navigation from leaking."""

    checkpoint = AccessCheckpoint(
        target_state="Report view",
        reconstruction_instructions=["Open report."],
        verification=["Heading visible."],
    )
    current_state = PageState("current", "https://example.test/report")
    preceding_state = PageState("before probe", "https://example.test/report")

    access = build_stage_messages("access", "task", [], current_state)
    discovery = build_stage_messages("discovery", "task", [], current_state)
    reconstruction = build_stage_messages(
        "reconstruction", "task", [], current_state, checkpoint=checkpoint
    )
    collection = build_stage_messages(
        "collection",
        "task",
        [],
        current_state,
        strategy="retained-final-document",
        preceding_state=preceding_state,
    )

    assert "Access checkpoint" not in access[1]["content"]
    assert "Access checkpoint" not in discovery[1]["content"]
    assert "Access checkpoint" in reconstruction[1]["content"]
    assert "Report view" in reconstruction[1]["content"]
    assert "Report view" not in collection[1]["content"]
    assert "retained-final-document" in collection[1]["content"]
    assert "before probe" in collection[1]["content"]
    assert "browser_navigate" not in collection[1]["content"]


def test_stage_prompts_define_page_retrieval_waiting_and_completion_contracts() -> None:
    """Each stage gets a focused system instruction and exactly two fresh messages."""

    state = PageState("snapshot", "https://example.test/")
    messages_by_stage = {
        "access": build_stage_messages("access", "task", [], state),
        "discovery": build_stage_messages("discovery", "task", [], state),
        "reconstruction": build_stage_messages(
            "reconstruction",
            "task",
            [],
            state,
            checkpoint=AccessCheckpoint(
                target_state="View",
                verification=["Visible."],
            ),
        ),
        "collection": build_stage_messages(
            "collection", "task", [], state, strategy="retained-final-document"
        ),
    }

    for messages in messages_by_stage.values():
        assert [message["role"] for message in messages] == ["system", "user"]
        assert "Complete only by calling complete_" in messages[0]["content"]
    assert "page/view retrieval" in messages_by_stage["access"][0]["content"]
    assert "unknown" in messages_by_stage["discovery"][0]["content"]
    assert "semantic waits" in messages_by_stage["collection"][0]["content"]


def test_stage_runner_rejects_ordinary_terminal_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stages never treat ordinary no-tool model text as success."""

    async def fake_stream_model_turn(*arguments: object) -> ModelTurn:
        return ModelTurn(content="done", tool_call=None, reasoning_fragments=())

    async def unused_action(*arguments: object) -> PageState:
        raise AssertionError("remote action should not execute")

    monkeypatch.setattr(agent_loop, "stream_model_turn", fake_stream_model_turn)

    with pytest.raises(MissingStageCompletionError, match="access stage"):
        asyncio.run(
            agent_loop.run_stage(
                llm_settings(),
                AgentSettings(),
                catalog(),
                ACCESS_COMPLETION_TOOL,
                "task",
                PageState("snapshot", "https://example.test/"),
                unused_action,
            )
        )


def test_stage_limits_allow_final_completion_and_reject_final_turn_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inclusive stage limits reserve the final model turn for required completion."""

    async def unused_action(*arguments: object) -> PageState:
        raise AssertionError("remote action should not execute")

    async def complete_access(*arguments: object) -> ModelTurn:
        return access_completion_turn()

    monkeypatch.setattr(agent_loop, "stream_model_turn", complete_access)
    result = asyncio.run(
        agent_loop.run_stage(
            llm_settings(),
            AgentSettings(max_model_turns=1),
            catalog(),
            ACCESS_COMPLETION_TOOL,
            "task",
            PageState("snapshot", "https://example.test/"),
            unused_action,
        )
    )
    completion_call = access_completion_turn().tool_call
    assert completion_call is not None
    assert result.report == ACCESS_COMPLETION_TOOL.parse(completion_call.arguments)

    remote_turn = ModelTurn(
        content="",
        tool_call=RequestedToolCall("browser_type", "call-1", {}),
        reasoning_fragments=(),
    )

    async def request_remote_action(*arguments: object) -> ModelTurn:
        return remote_turn

    monkeypatch.setattr(agent_loop, "stream_model_turn", request_remote_action)
    with pytest.raises(ExecutionLimitError, match="final model turn"):
        asyncio.run(
            agent_loop.run_stage(
                llm_settings(),
                AgentSettings(max_model_turns=1),
                catalog(),
                ACCESS_COMPLETION_TOOL,
                "task",
                PageState("snapshot", "https://example.test/"),
                unused_action,
            )
        )


def test_stage_action_limits_are_independent_for_each_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A new stage begins with fresh action counters rather than borrowing another stage's quota."""

    remote_turn = ModelTurn(
        content="",
        tool_call=RequestedToolCall("browser_type", "call-1", {}),
        reasoning_fragments=(),
    )
    completion_turns = {
        "complete_access": access_completion_turn(),
        "complete_discovery": ModelTurn(
            content="",
            tool_call=RequestedToolCall(
                "complete_discovery",
                "call-complete",
                {"strategy": "retained-final-document", "evidence": ["Static."]},
                "completion",
            ),
            reasoning_fragments=(),
        ),
    }
    turns = iter(
        [
            remote_turn,
            completion_turns["complete_access"],
            remote_turn,
            completion_turns["complete_discovery"],
        ]
    )
    action_count = 0

    async def fake_stream_model_turn(*arguments: object) -> ModelTurn:
        return next(turns)

    async def execute_action(*arguments: object) -> PageState:
        nonlocal action_count
        action_count += 1
        return PageState(f"snapshot {action_count}", "https://example.test/")

    monkeypatch.setattr(agent_loop, "stream_model_turn", fake_stream_model_turn)
    settings = AgentSettings(max_model_turns=2, max_browser_actions=1)
    first_result = asyncio.run(
        agent_loop.run_stage(
            llm_settings(),
            settings,
            catalog(),
            ACCESS_COMPLETION_TOOL,
            "task",
            PageState("initial", "https://example.test/"),
            execute_action,
        )
    )
    asyncio.run(
        agent_loop.run_stage(
            llm_settings(),
            settings,
            catalog(),
            DISCOVERY_COMPLETION_TOOL,
            "task",
            first_result.page_state,
            execute_action,
        )
    )

    assert action_count == 2


def test_stage_context_requires_only_its_own_completion_inputs() -> None:
    """The runner's completion schemas stay tied to their matching named stages."""

    assert ACCESS_COMPLETION_TOOL.stage_name == "access"
    assert DISCOVERY_COMPLETION_TOOL.stage_name == "discovery"
    assert RECONSTRUCTION_COMPLETION_TOOL.stage_name == "reconstruction"
    assert COLLECTION_COMPLETION_TOOL.stage_name == "collection"
