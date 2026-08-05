"""Typed model-stage execution for greedy browser collection."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .agent_context import PageState, build_stage_messages, format_browser_action
from .config import AgentSettings, LlmSettings
from .errors import ExecutionLimitError, MissingStageCompletionError, ModelStreamError
from .model_stream import stream_model_turn
from .playwright_tools import ToolCatalog
from .reasoning_progress import ReasoningProgressReporter
from .stage_models import AccessCheckpoint, CompletionTool, DiscoveryStrategy, StageReportValue

BrowserAction = Callable[[str, dict[str, object]], Awaitable[PageState]]


@dataclass(frozen=True)
class StageRunResult:
    """A validated completion report and the final fresh state for one stage."""

    report: StageReportValue
    page_state: PageState


async def run_stage(
    llm_settings: LlmSettings,
    agent_settings: AgentSettings,
    tool_catalog: ToolCatalog,
    completion_tool: CompletionTool,
    task: str,
    initial_state: PageState,
    execute_browser_action: BrowserAction,
    reasoning_progress: ReasoningProgressReporter | None = None,
    checkpoint: AccessCheckpoint | None = None,
    strategy: DiscoveryStrategy | None = None,
) -> StageRunResult:
    """Run fresh model turns until one stage submits its required local completion tool."""

    stage_catalog = tool_catalog.with_completion_tool(completion_tool)
    action_log: list[str] = []
    current_state = initial_state
    preceding_state: PageState | None = None
    browser_action_count = 0

    for turn_index in range(agent_settings.max_model_turns):
        messages = build_stage_messages(
            completion_tool.stage_name,
            task,
            action_log,
            current_state,
            checkpoint,
            strategy,
            preceding_state,
        )
        try:
            async with asyncio.timeout(agent_settings.model_request_timeout_seconds):
                if reasoning_progress is None:
                    model_turn = await stream_model_turn(llm_settings, stage_catalog, messages)
                else:
                    model_turn = await stream_model_turn(
                        llm_settings,
                        stage_catalog,
                        messages,
                        reasoning_progress.accept,
                    )
        except TimeoutError as error:
            raise ExecutionLimitError("Model request time limit exceeded.") from error
        if reasoning_progress is not None:
            await reasoning_progress.flush()
        if model_turn.tool_call is None:
            raise MissingStageCompletionError(
                f"The {completion_tool.stage_name} stage stopped without its required "
                "completion tool."
            )
        if model_turn.tool_call.kind == "completion":
            report = completion_tool.parse(model_turn.tool_call.arguments)
            return StageRunResult(report, current_state)
        if model_turn.tool_call.kind != "remote":
            raise ModelStreamError("Model requested an unsupported tool-call route.")
        if turn_index == agent_settings.max_model_turns - 1:
            raise ExecutionLimitError(
                "A browser action was requested on the final model turn, leaving no turn for "
                "mandatory stage completion."
            )
        if browser_action_count >= agent_settings.max_browser_actions:
            raise ExecutionLimitError("Browser action limit exceeded.")
        remote_name = tool_catalog.remote_name_by_model_name[model_turn.tool_call.model_tool_name]
        preceding_state = current_state
        current_state = await execute_browser_action(remote_name, model_turn.tool_call.arguments)
        action_log.append(
            format_browser_action(remote_name, model_turn.tool_call.arguments, current_state)
        )
        browser_action_count += 1

    raise ExecutionLimitError("Model-turn limit exceeded.")
