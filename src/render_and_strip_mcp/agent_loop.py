"""Model-directed sequential browser-action loop."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from .agent_context import BrowserActionResult, build_model_messages, format_browser_action
from .config import AgentSettings, LlmSettings
from .errors import ExecutionLimitError
from .model_stream import stream_model_turn
from .playwright_tools import ToolCatalog
from .reasoning_progress import ReasoningProgressReporter

BrowserAction = Callable[[str, dict[str, object]], Awaitable[BrowserActionResult]]


async def run_agent_loop(
    llm_settings: LlmSettings,
    agent_settings: AgentSettings,
    tool_catalog: ToolCatalog,
    task: str,
    initial_url: str,
    initial_observation: str,
    execute_browser_action: BrowserAction,
    initial_action_log: list[str] | None = None,
    reasoning_progress: ReasoningProgressReporter | None = None,
) -> BrowserActionResult:
    """Run fresh model turns until normal completion, returning final page state."""

    action_log = list(initial_action_log or [])
    current_url = initial_url
    newest_observation = initial_observation
    browser_action_count = 0

    for _ in range(agent_settings.max_model_turns):
        messages = build_model_messages(task, action_log, current_url, newest_observation)
        try:
            async with asyncio.timeout(agent_settings.model_request_timeout_seconds):
                if reasoning_progress is None:
                    model_turn = await stream_model_turn(llm_settings, tool_catalog, messages)
                else:
                    model_turn = await stream_model_turn(
                        llm_settings,
                        tool_catalog,
                        messages,
                        reasoning_progress.accept,
                    )
        except TimeoutError as error:
            raise ExecutionLimitError("Model request time limit exceeded.") from error
        if reasoning_progress is not None:
            await reasoning_progress.flush()
        if model_turn.tool_call is None:
            return BrowserActionResult(
                observation=newest_observation,
                current_url=current_url,
            )
        if browser_action_count >= agent_settings.max_browser_actions:
            raise ExecutionLimitError("Browser action limit exceeded.")
        browser_action_count += 1
        remote_name = tool_catalog.remote_name_by_model_name[model_turn.tool_call.model_tool_name]
        action_result = await execute_browser_action(remote_name, model_turn.tool_call.arguments)
        action_log.append(
            format_browser_action(remote_name, model_turn.tool_call.arguments, action_result)
        )
        current_url = action_result.current_url
        newest_observation = action_result.observation

    raise ExecutionLimitError("Model-turn limit exceeded.")
