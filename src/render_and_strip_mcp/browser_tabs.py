"""Official Playwright MCP tab-list parsing and original-tab restoration."""

from __future__ import annotations

import re
from dataclasses import dataclass

from fastmcp import Client

from .errors import BrowserAgentError
from .mcp_results import extract_text_result

TAB_LINE = re.compile(
    r"^- (?P<index>\d+): (?P<current>\(current\) )?\[(?P<title>.*?)\]\((?P<url>.*?)\)$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class BrowserTab:
    """One tab described by the official browser_tabs list response."""

    index: int
    is_current: bool
    url: str


async def list_browser_tabs(client: Client, timeout_seconds: float) -> list[BrowserTab]:
    """List tabs through the pinned browser_tabs list operation."""

    result = await client.call_tool("browser_tabs", {"action": "list"}, timeout=timeout_seconds)
    tabs = [
        BrowserTab(
            index=int(tab_match.group("index")),
            is_current=tab_match.group("current") is not None,
            url=tab_match.group("url"),
        )
        for tab_match in TAB_LINE.finditer(extract_text_result(result))
    ]
    if not tabs:
        raise BrowserAgentError("Playwright MCP reported no parseable open tabs.")
    return tabs


async def select_original_tab(
    client: Client,
    original_tab_index: int,
    timeout_seconds: float,
) -> BrowserTab:
    """Restore the original tab or fail when it no longer exists."""

    tabs = await list_browser_tabs(client, timeout_seconds)
    original_tab = next((tab for tab in tabs if tab.index == original_tab_index), None)
    if original_tab is None:
        raise BrowserAgentError("The original browser tab was closed.")
    if not original_tab.is_current:
        result = await client.call_tool(
            "browser_tabs",
            {"action": "select", "index": original_tab_index},
            timeout=timeout_seconds,
        )
        extract_text_result(result)
    return original_tab


def current_tab_index(tabs: list[BrowserTab]) -> int:
    """Return the currently selected initial tab index from a tab-list response."""

    current_tab = next((tab for tab in tabs if tab.is_current), None)
    if current_tab is None:
        raise BrowserAgentError("Playwright MCP tab list has no current tab.")
    return current_tab.index
