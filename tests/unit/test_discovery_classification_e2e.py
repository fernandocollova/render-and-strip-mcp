"""Deterministic end-to-end coverage for model-guided discovery classification."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from contextlib import asynccontextmanager

import pytest
from fastmcp.client.client import CallToolResult
from mcp.types import TextContent

import render_and_strip_mcp.agent_loop as agent_loop
import render_and_strip_mcp.browser_agent as browser_agent_module
from render_and_strip_mcp.browser_agent import BrowserAgent
from render_and_strip_mcp.config import Settings
from render_and_strip_mcp.errors import UnknownDiscoveryStrategyError
from render_and_strip_mcp.model_stream import ModelTurn, RequestedToolCall
from render_and_strip_mcp.playwright_tools import PlaywrightSession, ToolCatalog

from .test_browser_agent import RecordingProgressReporter

REPORT_URL = "https://example.test/reports"


def settings() -> Settings:
    """Build settings for deterministic full-pipeline classification tests."""

    return Settings.model_validate(
        {
            "playwright_mcp": {"endpoint": "https://browser.example/mcp"},
            "llm": {
                "model": "test-model",
                "api_base": "https://model.example/v1",
                "api_key": "test-key",
            },
        }
    )


def text_result(text: str) -> CallToolResult:
    """Return a successful text response in the official MCP result shape."""

    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=None,
        meta=None,
    )


class CategorizationBrowserClient:
    """Browser state that models finite scroll and numbered replacement pagination."""

    def __init__(self, page_kind: str):
        self.page_kind = page_kind
        self.has_revealed_increment = False
        self.navigation_count = 0
        self.document_requests = 0

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, object],
        **kwargs: object,
    ) -> CallToolResult:
        if tool_name == "browser_navigate":
            assert arguments == {"url": REPORT_URL}
            self.navigation_count += 1
            self.has_revealed_increment = False
            return text_result(self._snapshot())
        if tool_name == "browser_tabs":
            if arguments["action"] == "list":
                return text_result(
                    "### Result\n- 0: (current) [Reports](https://example.test/reports)"
                )
            assert arguments == {"action": "select", "index": 0}
            return text_result("### Result\n- 0: (current) [Reports](https://example.test/reports)")
        if tool_name == "browser_snapshot":
            assert arguments == {}
            return text_result(self._snapshot())
        if tool_name == "browser_press_key":
            assert self.page_kind == "incremental"
            assert arguments == {"key": "End"}
            self.has_revealed_increment = True
            return text_result("### Page\n- Scroll action completed")
        if tool_name == "browser_evaluate":
            function = arguments["function"]
            if function == "() => location.href":
                return text_result(f"### Result\n{json.dumps(REPORT_URL)}\n### Ran Playwright code")
            self.document_requests += 1
            return text_result(f"### Result\n{json.dumps(self._document_html())}")
        if tool_name == "browser_close":
            return text_result("Browser closed")
        raise AssertionError(f"Unexpected browser tool {tool_name}")

    def _snapshot(self) -> str:
        if self.page_kind == "numbered":
            return (
                "### Page\n# Reports\n- Page 1 of 3\n- [1] current\n"
                "- [2] next page replaces the current document\n- Next page"
            )
        if self.has_revealed_increment:
            return "### Page\n# Reports\n- Item 1\n- Item 2\n- End of reports"
        return "### Page\n# Reports\n- Item 1\n- Scroll down to load more reports"

    def _document_html(self) -> str:
        additional_item = "<p>Item 2</p>" if self.has_revealed_increment else ""
        return f"<html><head></head><body><main><p>Item 1</p>{additional_item}</main></body></html>"


def install_browser_session(
    monkeypatch: pytest.MonkeyPatch, client: CategorizationBrowserClient
) -> None:
    """Connect the real browser agent to the deterministic browser boundary."""

    @asynccontextmanager
    async def fake_session(endpoint: str):
        yield PlaywrightSession(
            client=client,  # type: ignore[arg-type]
            tool_catalog=ToolCatalog([], {"browser_press_key": "browser_press_key"}),
        )

    monkeypatch.setattr(browser_agent_module, "open_playwright_session", fake_session)


def install_categorizing_model(
    monkeypatch: pytest.MonkeyPatch,
    page_kind: str,
) -> list[str]:
    """Use observations to produce deterministic discovery conclusions at the model boundary."""

    stage_turn_counts: defaultdict[str, int] = defaultdict(int)
    reported_strategies: list[str] = []

    async def fake_stream_model_turn(
        llm_settings: object,
        tool_catalog: ToolCatalog,
        messages: list[dict[str, str]],
        on_reasoning_fragment: object,
    ) -> ModelTurn:
        assert callable(on_reasoning_fragment)
        completion_tool = tool_catalog.completion_tool
        assert completion_tool is not None
        stage_name = completion_tool.name.removeprefix("complete_")
        stage_turn_counts[stage_name] += 1
        user_message = messages[1]["content"]

        if stage_name == "access":
            return _completion_turn(
                "complete_access",
                {
                    "target_state": "Reports view",
                    "reconstruction_instructions": [],
                    "verification": ["The reports heading is visible."],
                },
            )
        if stage_name == "discovery" and page_kind == "numbered":
            assert "next page replaces the current document" in user_message
            reported_strategies.append("unknown")
            return _completion_turn(
                "complete_discovery",
                {
                    "strategy": "unknown",
                    "evidence": ["Numbered next-page navigation replaces the current document."],
                },
            )
        if stage_name == "discovery":
            if stage_turn_counts[stage_name] == 1:
                assert "Scroll down to load more reports" in user_message
                return _remote_turn("browser_press_key", {"key": "End"})
            assert "Item 2" in user_message
            reported_strategies.append("retained-final-document")
            return _completion_turn(
                "complete_discovery",
                {
                    "strategy": "retained-final-document",
                    "evidence": ["Scrolling appended Item 2 while Item 1 remained visible."],
                },
            )
        if stage_name == "reconstruction":
            assert "Reports view" in user_message
            return _completion_turn(
                "complete_reconstruction",
                {"verified": True, "evidence": ["The reports heading is visible."]},
            )
        if stage_name == "collection":
            if stage_turn_counts[stage_name] == 1:
                assert "Scroll down to load more reports" in user_message
                return _remote_turn("browser_press_key", {"key": "End"})
            assert "Item 1" in user_message and "Item 2" in user_message
            return _completion_turn(
                "complete_collection",
                {
                    "complete": True,
                    "evidence": ["The observed end retains both report items."],
                },
            )
        raise AssertionError(f"Unexpected model stage {stage_name}")

    monkeypatch.setattr(agent_loop, "stream_model_turn", fake_stream_model_turn)
    return reported_strategies


def _completion_turn(tool_name: str, arguments: dict[str, object]) -> ModelTurn:
    """Build a locally routed completion-tool response for the deterministic model."""

    return ModelTurn(
        content="",
        tool_call=RequestedToolCall(tool_name, f"{tool_name}-call", arguments, "completion"),
        reasoning_fragments=(),
    )


def _remote_turn(tool_name: str, arguments: dict[str, object]) -> ModelTurn:
    """Build one eligible model-directed browser-action response."""

    return ModelTurn(
        content="",
        tool_call=RequestedToolCall(tool_name, f"{tool_name}-call", arguments),
        reasoning_fragments=(),
    )


def test_end_to_end_finite_incremental_scroll_is_retained_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A finite scroll discovery probe and collection pass retain both items in final HTML."""

    client = CategorizationBrowserClient("incremental")
    install_browser_session(monkeypatch, client)
    reported_strategies = install_categorizing_model(monkeypatch, "incremental")

    document_html = asyncio.run(
        BrowserAgent(
            settings(),
            RecordingProgressReporter(),  # type: ignore[arg-type]
        ).run(REPORT_URL, "Retrieve reports")
    )

    assert reported_strategies == ["retained-final-document"]
    assert "Item 1" in document_html
    assert "Item 2" in document_html
    assert client.navigation_count == 2
    assert client.document_requests == 1


def test_end_to_end_numbered_replacement_pagination_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Numbered replacement pagination fails before reset, collection, or partial extraction."""

    client = CategorizationBrowserClient("numbered")
    install_browser_session(monkeypatch, client)
    reported_strategies = install_categorizing_model(monkeypatch, "numbered")

    with pytest.raises(UnknownDiscoveryStrategyError, match="could not establish"):
        asyncio.run(
            BrowserAgent(
                settings(),
                RecordingProgressReporter(),  # type: ignore[arg-type]
            ).run(REPORT_URL, "Retrieve reports")
        )

    assert reported_strategies == ["unknown"]
    assert client.navigation_count == 1
    assert client.document_requests == 0
