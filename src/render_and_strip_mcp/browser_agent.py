"""Concrete orchestration of one isolated Playwright MCP browser-agent session."""

from __future__ import annotations

import asyncio
import logging
from typing import cast

import litellm
from fastmcp import Client
from fastmcp.exceptions import ToolError
from openai import OpenAIError

from .agent_context import AccessStage, DiscoveryStage, PageState, ReconstructionStage
from .agent_loop import StageRunner
from .browser_tabs import current_tab_index, list_browser_tabs, select_original_tab
from .collection_strategy import COLLECTION_STRATEGIES
from .config import Settings
from .errors import (
    BrowserAgentError,
    ExecutionLimitError,
    UnknownDiscoveryStrategyError,
    UnsuccessfulStageOutcomeError,
)
from .html_cleaner import normalize_captured_content
from .mcp_results import extract_json_string_result, extract_text_result
from .playwright_tools import PlaywrightSession, open_playwright_session
from .reasoning_progress import IdleAwareReasoningProgressReporter, ReasoningProgressReporter
from .selected_content import CapturedContent, fetch_visible_selected_region
from .stage_models import (
    AccessCheckpoint,
    CollectionStrategy,
    DiscoveryReport,
    ReconstructionReport,
    SelectedRegion,
)
from .url_policy import UrlPolicy

logger = logging.getLogger(__name__)


class BrowserAgent:
    """Run greedy staged browser collection in an isolated remote Playwright session."""

    def __init__(self, settings: Settings, reasoning_progress: ReasoningProgressReporter):
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
                timeout = asyncio.timeout(self._settings.agent.idle_timeout_seconds)
                async with timeout as idle_timeout:
                    invocation_progress = IdleAwareReasoningProgressReporter(
                        self._reasoning_progress,
                        idle_timeout,
                        self._settings.agent.idle_timeout_seconds,
                    )
                    if not task.strip():
                        raise BrowserAgentError("The browser task must not be empty.")
                    UrlPolicy(url, self._settings.agent.allow_plain_http).validate_initial_url()
                    session_manager = open_playwright_session(
                        str(self._settings.playwright_mcp.endpoint)
                    )
                    session = await session_manager.__aenter__()
                    final_html = await self._run_session(session, url, task, invocation_progress)
            except TimeoutError as error:
                raise ExecutionLimitError("Agent idle time limit exceeded.") from error
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
            await self._reasoning_progress.flush_if_needed()
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

    async def _run_session(
        self,
        session: PlaywrightSession,
        url: str,
        task: str,
        progress: IdleAwareReasoningProgressReporter,
    ) -> str:
        """Run all greedy stages, then clean the successfully captured documents."""

        await progress.accept_operational_status("Initial navigation")
        initial_navigation = await session.client.call_tool(
            "browser_navigate",
            {"url": url},
            timeout=self._settings.agent.navigation_timeout_seconds,
        )
        extract_text_result(initial_navigation)
        original_tab_index = current_tab_index(
            await list_browser_tabs(
                session.client,
                self._settings.agent.browser_action_timeout_seconds,
            )
        )
        initial_url = await self._current_url(session.client)
        url_policy = UrlPolicy(initial_url, self._settings.agent.allow_plain_http)
        url_policy.validate_initial_url()
        initial_state = await self._capture_fresh_page_state(
            session.client,
            original_tab_index,
            url_policy,
        )

        async def execute_browser_action(tool_name: str, arguments: dict[str, object]) -> PageState:
            return await self._execute_browser_action(
                session.client,
                tool_name,
                arguments,
                original_tab_index,
                url_policy,
            )

        stage_runner = StageRunner(
            self._settings.llm,
            self._settings.agent,
            session.tool_catalog,
            execute_browser_action,
            progress,
        )

        await progress.accept_operational_status("Access")
        access_result = await stage_runner.run(
            AccessStage(),
            task,
            initial_state,
        )
        checkpoint = cast(AccessCheckpoint, access_result.report)

        await progress.accept_operational_status("Discovery")
        discovery_result = await stage_runner.run(
            DiscoveryStage(),
            task,
            access_result.page_state,
        )
        discovery_report = cast(DiscoveryReport, discovery_result.report)
        if discovery_report.strategy == "unknown":
            raise UnknownDiscoveryStrategyError(
                "Discovery could not establish a supported collection strategy."
            )
        collection_strategy = cast(CollectionStrategy, discovery_report.strategy)

        await progress.accept_operational_status("Reset")
        reset_navigation = await session.client.call_tool(
            "browser_navigate",
            {"url": url},
            timeout=self._settings.agent.navigation_timeout_seconds,
        )
        extract_text_result(reset_navigation)
        reset_state = await self._capture_fresh_page_state(
            session.client,
            original_tab_index,
            url_policy,
        )

        await progress.accept_operational_status("Reconstruction")
        reconstruction_result = await stage_runner.run(
            ReconstructionStage(checkpoint),
            task,
            reset_state,
        )
        reconstruction_report = cast(ReconstructionReport, reconstruction_result.report)
        if not reconstruction_report.verified:
            raise UnsuccessfulStageOutcomeError(
                "Checkpoint reconstruction did not verify the target page state."
            )

        await progress.accept_operational_status("Collection")
        collection_handler = COLLECTION_STRATEGIES[collection_strategy]

        async def capture_content(selected_region: SelectedRegion) -> CapturedContent:
            return await self._capture_selected_content(
                session.client,
                original_tab_index,
                url_policy,
                selected_region,
            )

        captured_content = await collection_handler(
            stage_runner,
            task,
            reconstruction_result.page_state,
            capture_content,
            self._settings.agent.max_paginated_documents,
        )

        await progress.accept_operational_status("Final extraction and cleaning")
        return normalize_captured_content(
            captured_content,
            self._settings.agent.allow_plain_http,
            self._settings.output.max_html_bytes,
        )

    async def _capture_selected_content(
        self,
        client: Client,
        original_tab_index: int,
        url_policy: UrlPolicy,
        selected_region: SelectedRegion,
    ) -> CapturedContent:
        """Capture the selected current region before later actions can replace it."""

        await select_original_tab(
            client,
            original_tab_index,
            self._settings.agent.browser_action_timeout_seconds,
        )
        source_url = await self._current_url(client)
        url_policy.validate_observed_url(source_url)
        try:
            async with asyncio.timeout(self._settings.agent.browser_action_timeout_seconds):
                region_html = await fetch_visible_selected_region(
                    client,
                    selected_region,
                    self._settings.agent.browser_action_timeout_seconds,
                )
        except TimeoutError as error:
            raise ExecutionLimitError("Selected content extraction time limit exceeded.") from error
        return CapturedContent(region_html, source_url)

    async def _execute_browser_action(
        self,
        client: Client,
        tool_name: str,
        arguments: dict[str, object],
        original_tab_index: int,
        url_policy: UrlPolicy,
    ) -> PageState:
        """Run one model action and discard its stale result in favor of a fresh snapshot."""

        timeout_seconds = (
            self._settings.agent.navigation_timeout_seconds
            if tool_name in {"browser_navigate", "browser_navigate_back"}
            else self._settings.agent.browser_action_timeout_seconds
        )
        action_result = await client.call_tool(tool_name, arguments, timeout=timeout_seconds)
        extract_text_result(action_result)
        return await self._capture_fresh_page_state(client, original_tab_index, url_policy)

    async def _capture_fresh_page_state(
        self,
        client: Client,
        original_tab_index: int,
        url_policy: UrlPolicy,
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
        url_policy.validate_observed_url(current_url)
        snapshot = await client.call_tool(
            "browser_snapshot",
            {},
            timeout=self._settings.agent.browser_action_timeout_seconds,
        )
        return PageState(extract_text_result(snapshot), current_url)

    async def _current_url(self, client: Client) -> str:
        """Read the tracked page's documented top-level location through browser_evaluate."""

        result = await client.call_tool(
            "browser_evaluate",
            {"function": "() => location.href"},
            timeout=self._settings.agent.browser_action_timeout_seconds,
        )
        return extract_json_string_result(result)

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
        extract_text_result(close_result)
