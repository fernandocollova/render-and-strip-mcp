"""Tests for compact stage context and bounded typed stage execution."""

from __future__ import annotations

import asyncio

import pytest

import render_and_strip_mcp.agent_loop as agent_loop
from render_and_strip_mcp.agent_context import (
    AccessStage,
    CollectionStage,
    DiscoveryStage,
    PageState,
    PaginationAdvanceStage,
    ReconstructionStage,
)
from render_and_strip_mcp.config import AgentSettings, LlmSettings
from render_and_strip_mcp.errors import ExecutionLimitError, MissingStageCompletionError
from render_and_strip_mcp.model_stream import ModelTurn, RequestedToolCall
from render_and_strip_mcp.playwright_tools import ToolCatalog
from render_and_strip_mcp.stage_models import (
    ACCESS_COMPLETION_TOOL,
    COLLECTION_COMPLETION_TOOL,
    DISCOVERY_COMPLETION_TOOL,
    PAGINATION_ADVANCE_COMPLETION_TOOL,
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


def stage_runner(
    execute_browser_action: agent_loop.BrowserAction,
    reasoning_progress: RecordingProgressReporter,
    agent_settings: AgentSettings | None = None,
) -> agent_loop.StageRunner:
    """Build one reusable runner with stable test dependencies."""

    return agent_loop.StageRunner(
        llm_settings(),
        AgentSettings() if agent_settings is None else agent_settings,
        catalog(),
        execute_browser_action,
        reasoning_progress,  # type: ignore[arg-type]
    )


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
        stage_runner(execute_browser_action, RecordingProgressReporter()).run(
            AccessStage(),
            "Complete the task",
            PageState("initial snapshot", "https://example.test/"),
        )
    )

    assert result.page_state == PageState("new snapshot", "https://example.test/next")
    assert result.browser_action_count == 1
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
        stage_runner(unused_action, reporter).run(
            AccessStage(),
            "task",
            PageState("snapshot", "https://example.test/"),
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

    access = AccessStage().build_messages("task", [], current_state)
    discovery = DiscoveryStage().build_messages("task", [], current_state)
    reconstruction = ReconstructionStage(checkpoint).build_messages("task", [], current_state)
    collection = CollectionStage("retained-final-document").build_messages(
        "task",
        [],
        current_state,
        preceding_state=preceding_state,
    )
    pagination = PaginationAdvanceStage(
        captured_region_count=3,
        progress="Pages 1-3 cover releases through version 2.0.",
    ).build_messages(
        "task",
        [],
        current_state,
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
    assert "Report view" not in pagination[1]["content"]
    assert "Captured region count:\n3" in pagination[1]["content"]
    assert "Pages 1-3 cover releases through version 2.0." in pagination[1]["content"]
    assert "before probe" in pagination[1]["content"]


def test_stage_prompts_define_page_retrieval_waiting_and_completion_contracts() -> None:
    """Each stage gets a focused system instruction and exactly two fresh messages."""

    state = PageState("snapshot", "https://example.test/")
    messages_by_stage = {
        "access": AccessStage().build_messages("task", [], state),
        "discovery": DiscoveryStage().build_messages("task", [], state),
        "reconstruction": ReconstructionStage(
            AccessCheckpoint(
                target_state="View",
                verification=["Visible."],
            )
        ).build_messages(
            "task",
            [],
            state,
        ),
        "collection": CollectionStage("retained-final-document").build_messages("task", [], state),
        "pagination": PaginationAdvanceStage(1).build_messages("task", [], state),
    }

    for messages in messages_by_stage.values():
        assert [message["role"] for message in messages] == ["system", "user"]
        assert "Complete only by calling complete_" in messages[0]["content"]
    assert "page/view retrieval" in messages_by_stage["access"][0]["content"]
    discovery_prompt = messages_by_stage["discovery"][0]["content"]
    assert "Ignore controls not plausibly related" in discovery_prompt
    assert "scrolling, disclosure, additive loading" in discovery_prompt
    assert "Probe one transition at a time" in discovery_prompt
    assert "Do not submit forms" in discovery_prompt
    assert "create, update, or delete data" in discovery_prompt
    assert "An unrelated or redundant ambiguous control alone" in discovery_prompt
    assert "prevents establishing a complete supported collection path" in discovery_prompt
    assert "choose unknown" in discovery_prompt
    collection_prompt = messages_by_stage["collection"][0]["content"]
    assert "semantic waits" in collection_prompt
    assert "exactly one current contiguous element" in collection_prompt
    assert "Exclude surrounding page-level header" in collection_prompt
    assert "do not select the full body as a fallback" in collection_prompt
    pagination_prompt = messages_by_stage["pagination"][0]["content"]
    assert pagination_prompt.startswith(
        "Assess whether pagination should stop at the current result page or advance exactly one"
    )
    assert "has been captured" not in pagination_prompt
    assert "natural terminal page" in pagination_prompt
    assert "uncertain, continue" in pagination_prompt
    assert "Read more" in pagination_prompt
    assert "site-, date-, or record-specific parsing" in pagination_prompt


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
            stage_runner(unused_action, RecordingProgressReporter()).run(
                AccessStage(),
                "task",
                PageState("snapshot", "https://example.test/"),
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
        stage_runner(
            unused_action,
            RecordingProgressReporter(),
            AgentSettings(max_model_turns=1),
        ).run(
            AccessStage(),
            "task",
            PageState("snapshot", "https://example.test/"),
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
            stage_runner(
                unused_action,
                RecordingProgressReporter(),
                AgentSettings(max_model_turns=1),
            ).run(
                AccessStage(),
                "task",
                PageState("snapshot", "https://example.test/"),
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

    observed_messages: list[str] = []

    async def fake_stream_model_turn(*arguments: object) -> ModelTurn:
        observed_messages.append(arguments[2][1]["content"])  # type: ignore[index]
        return next(turns)

    async def execute_action(*arguments: object) -> PageState:
        nonlocal action_count
        action_count += 1
        return PageState(f"snapshot {action_count}", "https://example.test/")

    monkeypatch.setattr(agent_loop, "stream_model_turn", fake_stream_model_turn)
    settings = AgentSettings(max_model_turns=2, max_browser_actions=1)
    runner = stage_runner(execute_action, RecordingProgressReporter(), settings)
    first_result = asyncio.run(
        runner.run(
            AccessStage(),
            "task",
            PageState("initial", "https://example.test/"),
        )
    )
    asyncio.run(
        runner.run(
            DiscoveryStage(),
            "task",
            first_result.page_state,
        )
    )

    assert action_count == 2
    assert "Actions:\n(no model-directed actions yet)" in observed_messages[2]


def test_stage_classes_own_their_matching_completion_tools() -> None:
    """Each concrete stage owns its identity and matching completion contract."""

    checkpoint = AccessCheckpoint(target_state="View", verification=["Visible."])

    assert AccessStage().stage_name == "access"
    assert DiscoveryStage().stage_name == "discovery"
    assert ReconstructionStage(checkpoint).stage_name == "reconstruction"
    assert CollectionStage("retained-final-document").stage_name == "collection"
    assert PaginationAdvanceStage(1).stage_name == "pagination-advance"
    assert AccessStage().completion_tool is ACCESS_COMPLETION_TOOL
    assert DiscoveryStage().completion_tool is DISCOVERY_COMPLETION_TOOL
    assert ReconstructionStage(checkpoint).completion_tool is RECONSTRUCTION_COMPLETION_TOOL
    assert CollectionStage("retained-final-document").completion_tool is COLLECTION_COMPLETION_TOOL
    assert PaginationAdvanceStage(1).completion_tool is PAGINATION_ADVANCE_COMPLETION_TOOL
    assert not hasattr(ACCESS_COMPLETION_TOOL, "stage_name")
