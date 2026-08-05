"""Concrete orchestration of one isolated Playwright MCP browser-agent session."""

from __future__ import annotations

import asyncio
import logging
from typing import cast

import litellm
from fastmcp import Client
from fastmcp.exceptions import ToolError
from openai import OpenAIError

from .agent_context import PageState
from .agent_loop import run_stage
from .browser_tabs import current_tab_index, list_browser_tabs, select_original_tab
from .collection_strategy import COLLECTION_STRATEGIES
from .config import Settings
from .errors import (
    BrowserAgentError,
    ExecutionLimitError,
    UnknownDiscoveryStrategyError,
    UnsuccessfulStageOutcomeError,
)
from .html_cleaner import clean_rendered_html
from .mcp_results import extract_json_string_result, extract_text_result
from .playwright_tools import PlaywrightSession, open_playwright_session
from .reasoning_progress import ReasoningProgressReporter
from .rendered_document import fetch_visible_top_level_document
from .stage_models import (
    ACCESS_COMPLETION_TOOL,
    DISCOVERY_COMPLETION_TOOL,
    RECONSTRUCTION_COMPLETION_TOOL,
    AccessCheckpoint,
    DiscoveryReport,
    ReconstructionReport,
)
from .url_policy import Origin, UrlPolicy

logger = logging.getLogger(__name__)


class BrowserAgent:
    """Run greedy staged browser collection in an isolated remote Playwright session."""

    def __init__(
        self,
        settings: Settings,
        reasoning_progress: ReasoningProgressReporter | None = None,
    ):
        self._settings = settings
        self._reasoning_progress = reasoning_progress

    async def run(self, url: str, task: str) -> str:
        """Complete greedy collection and return clean HTML from the final page state."""

        session: PlaywrightSession | None = None
        session_manager = None
        primary_error: BaseException | None = None
        final_html = ""
        try:
            try:
                async with asyncio.timeout(self._settings.agent.total_timeout_seconds):
                    if not task.strip():
                        raise BrowserAgentError("The browser task must not be empty.")
                    UrlPolicy(url, self._settings.agent.allow_plain_http).validate_initial_url()
                    session_manager = open_playwright_session(
                        str(self._settings.playwright_mcp.endpoint)
                    )
                    session = await session_manager.__aenter__()
                    final_html = await self._run_session(session, url, task)
            except TimeoutError as error:
                raise ExecutionLimitError("Total invocation time limit exceeded.") from error
        except litellm.ContextWindowExceededError as error:
            translated_error = BrowserAgentError(f"Model context exhausted: {error}")
            primary_error = translated_error
            raise translated_error from error
        except OpenAIError as error:
            translated_error = BrowserAgentError(str(error))
            primary_error = translated_error
            raise translated_error from error
        except ToolError as error:
            translated_error = BrowserAgentError(str(error))
            primary_error = translated_error
            raise translated_error from error
        except BaseException as error:
            primary_error = error
            raise
        finally:
            if self._reasoning_progress is not None:
                await self._reasoning_progress.flush()
            if session is not None:
                try:
                    await self._close_browser(session.client)
                except BaseException as cleanup_error:
                    if primary_error is None:
                        raise BrowserAgentError(
                            "Playwright browser cleanup failed."
                        ) from cleanup_error
                    logger.warning("Playwright browser cleanup failed: %s", cleanup_error)
            if session_manager is not None:
                await session_manager.__aexit__(None, None, None)
        return final_html

    async def _run_session(self, session: PlaywrightSession, url: str, task: str) -> str:
        """Run all greedy stages, then extract and clean the one complete final document."""

        await self._report_operational_status("Initial navigation")
        initial_navigation = await self._call_tool(
            session.client,
            "browser_navigate",
            {"url": url},
            self._settings.agent.navigation_timeout_seconds,
        )
        extract_text_result(initial_navigation)
        original_tab_index = current_tab_index(
            await list_browser_tabs(
                session.client,
                self._settings.agent.browser_action_timeout_seconds,
            )
        )
        initial_url = await self._current_url(session.client)
        initial_origin = UrlPolicy(
            initial_url,
            self._settings.agent.allow_plain_http,
        ).origin
        initial_state = await self._capture_fresh_page_state(
            session.client,
            original_tab_index,
            initial_origin,
        )

        async def execute_browser_action(tool_name: str, arguments: dict[str, object]) -> PageState:
            return await self._execute_browser_action(
                session.client,
                tool_name,
                arguments,
                original_tab_index,
                initial_origin,
            )

        await self._report_operational_status("Access")
        access_result = await run_stage(
            self._settings.llm,
            self._settings.agent,
            session.tool_catalog,
            ACCESS_COMPLETION_TOOL,
            task,
            initial_state,
            execute_browser_action,
            self._reasoning_progress,
        )
        checkpoint = cast(AccessCheckpoint, access_result.report)

        await self._report_operational_status("Discovery")
        discovery_result = await run_stage(
            self._settings.llm,
            self._settings.agent,
            session.tool_catalog,
            DISCOVERY_COMPLETION_TOOL,
            task,
            access_result.page_state,
            execute_browser_action,
            self._reasoning_progress,
        )
        discovery_report = cast(DiscoveryReport, discovery_result.report)
        if discovery_report.strategy == "unknown":
            raise UnknownDiscoveryStrategyError(
                "Discovery could not establish retained-final-document collection."
            )

        await self._report_operational_status("Reset")
        reset_navigation = await self._call_tool(
            session.client,
            "browser_navigate",
            {"url": url},
            self._settings.agent.navigation_timeout_seconds,
        )
        extract_text_result(reset_navigation)
        reset_state = await self._capture_fresh_page_state(
            session.client,
            original_tab_index,
            initial_origin,
        )

        await self._report_operational_status("Reconstruction")
        reconstruction_result = await run_stage(
            self._settings.llm,
            self._settings.agent,
            session.tool_catalog,
            RECONSTRUCTION_COMPLETION_TOOL,
            task,
            reset_state,
            execute_browser_action,
            self._reasoning_progress,
            checkpoint,
        )
        reconstruction_report = cast(ReconstructionReport, reconstruction_result.report)
        if not reconstruction_report.verified:
            raise UnsuccessfulStageOutcomeError(
                "Checkpoint reconstruction did not verify the target page state."
            )

        await self._report_operational_status("Collection")
        collection_handler = COLLECTION_STRATEGIES[discovery_report.strategy]
        await collection_handler(
            self._settings.llm,
            self._settings.agent,
            session.tool_catalog,
            task,
            reconstruction_result.page_state,
            execute_browser_action,
            self._reasoning_progress,
        )

        await self._report_operational_status("Final extraction and cleaning")
        await select_original_tab(
            session.client,
            original_tab_index,
            self._settings.agent.browser_action_timeout_seconds,
        )
        final_url = await self._current_url(session.client)
        UrlPolicy(final_url, self._settings.agent.allow_plain_http).validate_observed_url(
            initial_origin
        )
        try:
            async with asyncio.timeout(self._settings.agent.browser_action_timeout_seconds):
                document_html = await fetch_visible_top_level_document(
                    session.client,
                    self._settings.agent.browser_action_timeout_seconds,
                )
        except TimeoutError as error:
            raise ExecutionLimitError("Final document extraction time limit exceeded.") from error
        return clean_rendered_html(
            document_html,
            final_url,
            self._settings.agent.allow_plain_http,
            self._settings.output.max_html_bytes,
        )

    async def _execute_browser_action(
        self,
        client: Client,
        tool_name: str,
        arguments: dict[str, object],
        original_tab_index: int,
        initial_origin: Origin,
    ) -> PageState:
        """Run one model action and discard its stale result in favor of a fresh snapshot."""

        timeout_seconds = (
            self._settings.agent.navigation_timeout_seconds
            if tool_name in {"browser_navigate", "browser_navigate_back"}
            else self._settings.agent.browser_action_timeout_seconds
        )
        action_result = await self._call_tool(client, tool_name, arguments, timeout_seconds)
        extract_text_result(action_result)
        return await self._capture_fresh_page_state(client, original_tab_index, initial_origin)

    async def _capture_fresh_page_state(
        self,
        client: Client,
        original_tab_index: int,
        initial_origin: Origin,
    ) -> PageState:
        """Optionally settle, restore the original tab, validate it, and snapshot it afresh."""

        if self._settings.agent.page_settle_seconds:
            await asyncio.sleep(self._settings.agent.page_settle_seconds)
        await select_original_tab(
            client,
            original_tab_index,
            self._settings.agent.browser_action_timeout_seconds,
        )
        current_url = await self._current_url(client)
        UrlPolicy(current_url, self._settings.agent.allow_plain_http).validate_observed_url(
            initial_origin
        )
        snapshot = await self._call_tool(
            client,
            "browser_snapshot",
            {},
            self._settings.agent.browser_action_timeout_seconds,
        )
        return PageState(extract_text_result(snapshot), current_url)

    async def _current_url(self, client: Client) -> str:
        """Read the tracked page's documented top-level location through browser_evaluate."""

        result = await self._call_tool(
            client,
            "browser_evaluate",
            {"function": "() => location.href"},
            self._settings.agent.browser_action_timeout_seconds,
        )
        return extract_json_string_result(result)

    async def _call_tool(
        self,
        client: Client,
        tool_name: str,
        arguments: dict[str, object],
        timeout_seconds: float,
    ) -> object:
        """Apply a local deadline around one remote Playwright MCP call."""

        try:
            async with asyncio.timeout(timeout_seconds):
                result = await client.call_tool(tool_name, arguments, timeout=timeout_seconds)
        except TimeoutError as error:
            raise ExecutionLimitError(f"Playwright {tool_name} time limit exceeded.") from error
        if not hasattr(result, "content"):
            raise BrowserAgentError(
                "Playwright MCP returned an unsupported asynchronous task result."
            )
        return result

    async def _report_operational_status(self, status: str) -> None:
        """Forward an orchestration milestone without presenting it as model reasoning."""

        if self._reasoning_progress is not None:
            await self._reasoning_progress.accept_operational_status(status)

    async def _close_browser(self, client: Client) -> None:
        """Close the isolated remote browser exactly once, shielding it from cancellation."""

        close_task = asyncio.create_task(
            client.call_tool(
                "browser_close",
                {},
                timeout=self._settings.agent.cleanup_timeout_seconds,
            )
        )
        try:
            close_result = await asyncio.shield(
                asyncio.wait_for(close_task, timeout=self._settings.agent.cleanup_timeout_seconds)
            )
        except asyncio.CancelledError:
            await asyncio.shield(close_task)
            raise
        if not hasattr(close_result, "content"):
            raise BrowserAgentError("Playwright MCP returned an unsupported cleanup result.")
        extract_text_result(close_result)
