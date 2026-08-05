"""Tests for browser-session policy and cleanup behavior."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from mcp.types import CallToolResult, TextContent

import render_and_strip_mcp.browser_agent as browser_agent_module
from render_and_strip_mcp.agent_context import BrowserActionResult
from render_and_strip_mcp.config import Settings
from render_and_strip_mcp.errors import BrowserAgentError
from render_and_strip_mcp.playwright_tools import PlaywrightSession, ToolCatalog


def settings(**agent_values: object) -> Settings:
    """Build valid application settings with optional agent-policy overrides."""

    return Settings.model_validate(
        {
            "playwright_mcp": {"endpoint": "https://browser.example/mcp"},
            "llm": {
                "model": "test-model",
                "api_base": "https://model.example/v1",
                "api_key": "test-key",
            },
            "agent": agent_values,
        }
    )


def text_result(text: str, is_error: bool = False) -> CallToolResult:
    """Create a textual official-MCP result for fake remote calls."""

    return CallToolResult(content=[TextContent(type="text", text=text)], isError=is_error)


class FakeBrowserClient:
    """Minimal official-MCP behavior with an action-induced secondary tab."""

    def __init__(self, locations: list[str], cleanup_error: bool = False):
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._locations = iter(locations)
        self._action_completed = False
        self._original_tab_selected = False
        self._cleanup_error = cleanup_error

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, object],
        **kwargs: object,
    ) -> CallToolResult:
        self.calls.append((tool_name, arguments))
        if tool_name == "browser_navigate":
            return text_result("### Page\n- Page URL: https://example.test/start")
        if tool_name == "browser_tabs":
            if arguments["action"] == "select":
                self._original_tab_selected = True
                return text_result("### Result\n- 0: (current) [Start](https://example.test/start)")
            if self._action_completed and not self._original_tab_selected:
                return text_result(
                    "### Result\n- 0: [Start](https://example.test/start)\n"
                    "- 1: (current) [Popup](https://example.test/popup)"
                )
            return text_result("### Result\n- 0: (current) [Start](https://example.test/start)")
        if tool_name == "browser_evaluate":
            if arguments["function"] != "() => location.href":
                return text_result('### Result\n"<html><head></head><body>Done</body></html>"')
            return text_result(
                f"### Result\n{json.dumps(next(self._locations))}\n### Ran Playwright code"
            )
        if tool_name == "browser_close":
            return text_result("cleanup failed", is_error=self._cleanup_error)
        self._action_completed = True
        return text_result("### Page\n- Page URL: https://example.test/next")


def install_fake_session(
    monkeypatch: pytest.MonkeyPatch,
    client: FakeBrowserClient,
) -> None:
    """Replace the HTTP session opener with a deterministic session context."""

    @asynccontextmanager
    async def fake_session(endpoint: str):
        yield PlaywrightSession(
            client=client,  # type: ignore[arg-type]
            tool_catalog=ToolCatalog([], {"browser_click": "browser_click"}),
        )

    monkeypatch.setattr(browser_agent_module, "open_playwright_session", fake_session)


def test_agent_restores_original_tab_and_ignores_popup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Actions that open a popup restore the initially navigated tab before continuing."""

    client = FakeBrowserClient(
        ["https://example.test/start", "https://example.test/next", "https://example.test/next"]
    )
    install_fake_session(monkeypatch, client)

    async def fake_run_loop(*arguments: object) -> BrowserActionResult:
        execute_browser_action = arguments[6]
        assert callable(execute_browser_action)
        return await execute_browser_action("browser_click", {})

    monkeypatch.setattr(browser_agent_module, "run_agent_loop", fake_run_loop)

    final_url = asyncio.run(
        browser_agent_module.BrowserAgent(settings()).run("https://example.test/", "click")
    )

    assert "<body>Done</body>" in final_url
    assert ("browser_tabs", {"action": "select", "index": 0}) in client.calls
    assert client.calls[-1] == ("browser_close", {})


def test_agent_rejects_invalid_input_before_opening_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disallowed HTTP is rejected without connecting to the remote browser."""

    monkeypatch.setattr(
        browser_agent_module,
        "open_playwright_session",
        lambda endpoint: (_ for _ in ()).throw(AssertionError("session should not open")),
    )

    with pytest.raises(BrowserAgentError, match="Plain HTTP"):
        asyncio.run(
            browser_agent_module.BrowserAgent(settings()).run("http://example.test/", "task")
        )


def test_agent_rejects_cross_origin_action_and_still_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-action locations must remain at the origin established by initial navigation."""

    client = FakeBrowserClient(["https://example.test/start", "https://other.test/next"])
    install_fake_session(monkeypatch, client)

    async def fake_run_loop(*arguments: object) -> BrowserActionResult:
        execute_browser_action = arguments[6]
        assert callable(execute_browser_action)
        return await execute_browser_action("browser_click", {})

    monkeypatch.setattr(browser_agent_module, "run_agent_loop", fake_run_loop)

    with pytest.raises(BrowserAgentError, match="left the initial document origin"):
        asyncio.run(
            browser_agent_module.BrowserAgent(settings()).run("https://example.test/", "click")
        )

    assert client.calls[-1] == ("browser_close", {})


def test_cleanup_preserves_primary_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cleanup errors are logged without replacing an earlier processing failure."""

    client = FakeBrowserClient(["https://example.test/start"], cleanup_error=True)
    install_fake_session(monkeypatch, client)

    async def fail_run_loop(*arguments: object) -> BrowserActionResult:
        raise BrowserAgentError("primary failure")

    monkeypatch.setattr(browser_agent_module, "run_agent_loop", fail_run_loop)

    with pytest.raises(BrowserAgentError, match="primary failure"):
        asyncio.run(
            browser_agent_module.BrowserAgent(settings()).run("https://example.test/", "task")
        )

    assert "cleanup failed" in caplog.text
