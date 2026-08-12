"""Tests for the public HTML-only FastMCP tool registration."""

from __future__ import annotations

import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

import render_and_strip_mcp.server as server_module
from render_and_strip_mcp.config import Settings
from render_and_strip_mcp.errors import BrowserAgentError
from render_and_strip_mcp.mcp_results import extract_text_result
from render_and_strip_mcp.reasoning_progress import ProgressReporter


def settings() -> Settings:
    """Build valid app settings for local in-memory server tests."""

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


def test_registered_tool_returns_only_agent_html(monkeypatch: pytest.MonkeyPatch) -> None:
    """The public tool exposes only URL/task inputs and forwards clean HTML unchanged."""

    observed: dict[str, object] = {}

    class FakeBrowserAgent:
        def __init__(self, *arguments: object):
            observed["arguments"] = arguments

        async def run(self, url: str, task: str) -> str:
            observed["input"] = (url, task)
            return "<!doctype html>\n<html><head></head><body><p>Clean</p></body></html>"

    monkeypatch.setattr(server_module, "BrowserAgent", FakeBrowserAgent)
    server = server_module.create_server(settings())

    async def exercise() -> tuple[list[str], str]:
        async with Client(server) as client:
            tools = await client.list_tools()
            result = await client.call_tool(
                "render_and_strip_page",
                {"url": "https://example.test/", "task": "Read the page"},
            )
        return [tool.name for tool in tools], extract_text_result(result)

    tool_names, html = asyncio.run(exercise())

    assert tool_names == ["render_and_strip_page"]
    assert observed["input"] == ("https://example.test/", "Read the page")
    assert isinstance(observed["arguments"][1], ProgressReporter)  # type: ignore[index]
    assert html == "<!doctype html>\n<html><head></head><body><p>Clean</p></body></html>"


def test_registered_tool_translates_expected_agent_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expected domain failures become MCP tool errors instead of partial responses."""

    class FailingBrowserAgent:
        def __init__(self, *arguments: object):
            pass

        async def run(self, url: str, task: str) -> str:
            raise BrowserAgentError("initial URL rejected")

    monkeypatch.setattr(server_module, "BrowserAgent", FailingBrowserAgent)
    server = server_module.create_server(settings())

    async def exercise() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError, match="initial URL rejected"):
                await client.call_tool(
                    "render_and_strip_page",
                    {"url": "https://example.test/", "task": "Read the page"},
                )

    asyncio.run(exercise())
