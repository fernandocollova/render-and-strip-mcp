"""Typed model-stage execution for greedy browser collection."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from .agent_context import PageState, Stage, format_browser_action
from .config import AgentSettings, LlmSettings
from .errors import ExecutionLimitError, MissingStageCompletionError, ModelStreamError
from .model_stream import stream_model_turn
from .playwright_tools import ToolCatalog
from .reasoning_progress import ReasoningProgressReporter
from .stage_models import StageReportValue

BrowserAction = Callable[[str, dict[str, object]], Awaitable[PageState]]


@dataclass(frozen=True)
class StageRunResult:
    """A validated completion report and the final fresh state for one stage."""

    report: StageReportValue
    page_state: PageState
    browser_action_count: int = 0


@dataclass
class StageRunState:
    """Mutable state isolated to one stage-run invocation."""

    current_state: PageState
    preceding_state: PageState | None = None
    action_log: list[str] = field(default_factory=list)
    browser_action_count: int = 0


@dataclass(frozen=True)
class StageRunner:
    """Execute independent stages using stable dependencies from one browser session."""

    llm_settings: LlmSettings
    agent_settings: AgentSettings
    tool_catalog: ToolCatalog
    execute_browser_action: BrowserAction
    reasoning_progress: ReasoningProgressReporter

    async def run(
        self,
        stage: Stage,
        task: str,
        initial_state: PageState,
    ) -> StageRunResult:
        """Run fresh model turns until one stage submits its required local completion tool."""

        completion_tool = stage.completion_tool
        stage_catalog = self.tool_catalog.with_completion_tool(completion_tool)
        state = StageRunState(current_state=initial_state)

        for turn_index in range(self.agent_settings.max_model_turns):
            messages = stage.build_messages(
                task,
                state.action_log,
                state.current_state,
                state.preceding_state,
            )
            try:
                async with asyncio.timeout(self.agent_settings.model_request_timeout_seconds):
                    model_turn = await stream_model_turn(
                        self.llm_settings,
                        stage_catalog,
                        messages,
                        self.reasoning_progress.accept,
                    )
            except TimeoutError as error:
                raise ExecutionLimitError("Model request time limit exceeded.") from error
            await self.reasoning_progress.flush_if_needed()
            if model_turn.tool_call is None:
                raise MissingStageCompletionError(
                    f"The {stage.stage_name} stage stopped without its required "
                    "completion tool."
                )
            if model_turn.tool_call.kind == "completion":
                report = completion_tool.parse(model_turn.tool_call.arguments)
                return StageRunResult(report, state.current_state, state.browser_action_count)
            if model_turn.tool_call.kind != "remote":
                raise ModelStreamError("Model requested an unsupported tool-call route.")
            if turn_index == self.agent_settings.max_model_turns - 1:
                raise ExecutionLimitError(
                    "A browser action was requested on the final model turn, leaving no turn for "
                    "mandatory stage completion."
                )
            if state.browser_action_count >= self.agent_settings.max_browser_actions:
                raise ExecutionLimitError("Browser action limit exceeded.")
            remote_name = self.tool_catalog.remote_name_by_model_name[
                model_turn.tool_call.model_tool_name
            ]
            state.preceding_state = state.current_state
            state.current_state = await self.execute_browser_action(
                remote_name, model_turn.tool_call.arguments
            )
            state.action_log.append(
                format_browser_action(
                    remote_name, model_turn.tool_call.arguments, state.current_state
                )
            )
            state.browser_action_count += 1

        raise ExecutionLimitError("Model-turn limit exceeded.")
