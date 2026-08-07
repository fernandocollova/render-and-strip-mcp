"""Tests for Playwright tool-catalog construction."""

from __future__ import annotations

import asyncio

import pytest
from mcp.types import Tool

import render_and_strip_mcp.playwright_tools as playwright_tools
from render_and_strip_mcp.errors import (
    StageToolCollisionError,
    ToolSchemaError,
)
from render_and_strip_mcp.stage_models import ACCESS_COMPLETION_TOOL


def discovered_tools() -> list[Tool]:
    """Return built-in browser tools plus representative eligible actions."""

    return [
        Tool(name="browser_navigate", description="Navigate", inputSchema=object_schema("url")),
        Tool(name="browser_tabs", description="Tabs", inputSchema=object_schema("action")),
        Tool(name="browser_snapshot", description="Snapshot", inputSchema=object_schema()),
        Tool(
            name="browser_evaluate",
            description="Evaluate",
            inputSchema=object_schema("function"),
        ),
        Tool(name="browser_close", description="Close", inputSchema=object_schema()),
        Tool(name="browser_click", description="Click", inputSchema=object_schema("target")),
        Tool(
            name="browser_run_code_unsafe",
            description="Unsafe",
            inputSchema=object_schema("code"),
        ),
        Tool(name="browser_file_upload", description="Upload", inputSchema=object_schema("paths")),
        Tool(name="browser_drop", description="Drop", inputSchema=object_schema("data")),
        Tool(name="browser_install", description="Install", inputSchema=object_schema()),
    ]


def object_schema(*property_names: str) -> dict[str, object]:
    """Build a simple official-style JSON object schema."""

    return {
        "type": "object",
        "properties": {property_name: {"type": "string"} for property_name in property_names},
    }


def test_catalog_excludes_reserved_and_unsafe_tools() -> None:
    """Only eligible browser actions are exposed as callable model tools."""

    catalog = playwright_tools.build_tool_catalog(discovered_tools())

    assert catalog.remote_name_by_model_name == {
        "browser_click": "browser_click",
        "browser_evaluate": "browser_evaluate",
        "browser_navigate": "browser_navigate",
    }
    assert [tool["function"]["name"] for tool in catalog.openai_tools] == [
        "browser_click",
        "browser_evaluate",
        "browser_navigate",
    ]


def test_catalog_adds_local_completion_tool_without_exposing_or_rerouting_remote_tools() -> None:
    """Completion reports are handled locally while eligible browser tools remain remote."""

    catalog = playwright_tools.build_tool_catalog(discovered_tools()).with_completion_tool(
        ACCESS_COMPLETION_TOOL
    )

    assert catalog.completion_tool == ACCESS_COMPLETION_TOOL
    assert catalog.remote_name_by_model_name["browser_click"] == "browser_click"
    assert [tool["function"]["name"] for tool in catalog.openai_tools][-1] == "complete_access"


def test_catalog_rejects_local_completion_name_collision() -> None:
    """An official remote tool must not shadow the stage-local completion route."""

    tools = [
        *discovered_tools(),
        Tool(name="complete_access", description="Conflicting tool", inputSchema=object_schema()),
    ]
    catalog = playwright_tools.build_tool_catalog(tools)

    with pytest.raises(StageToolCollisionError, match="conflicts"):
        catalog.with_completion_tool(ACCESS_COMPLETION_TOOL)


def test_catalog_rejects_invalid_openai_tool_name() -> None:
    """An incompatible remote tool name fails instead of receiving a compatibility mapping."""

    tools = [*discovered_tools(), Tool(name="browser action", inputSchema=object_schema())]

    with pytest.raises(ToolSchemaError, match="invalid OpenAI function name"):
        playwright_tools.build_tool_catalog(tools)


def test_catalog_rejects_missing_tool_description() -> None:
    """Eligible tools must retain the official interface's non-empty description."""

    tools = [*discovered_tools(), Tool(name="browser_custom", inputSchema=object_schema())]

    with pytest.raises(ToolSchemaError, match="must have a description"):
        playwright_tools.build_tool_catalog(tools)


def test_catalog_rejects_nonportable_schema_keywords() -> None:
    """Unsupported schema semantics fail rather than being silently omitted."""

    tools = [
        *discovered_tools(),
        Tool(
            name="browser_custom",
            inputSchema={"type": "object", "properties": {}, "oneOf": []},
        ),
    ]

    with pytest.raises(ToolSchemaError, match="oneOf"):
        playwright_tools.build_tool_catalog(tools)


def test_open_session_uses_discovered_tools_without_capability_prevalidation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each opener creates one async client session and exposes its discovered catalog."""

    observed: list[object] = []

    class FakeClient:
        def __init__(self, endpoint: str):
            observed.append(endpoint)

        async def __aenter__(self) -> FakeClient:
            observed.append("enter")
            return self

        async def __aexit__(self, *arguments: object) -> None:
            observed.append("exit")

        async def list_tools(self) -> list[Tool]:
            observed.append("list")
            return [Tool(name="browser_click", description="Click", inputSchema=object_schema())]

    monkeypatch.setattr(playwright_tools, "Client", FakeClient)

    async def exercise() -> None:
        async with playwright_tools.open_playwright_session("http://browser.test/mcp") as session:
            assert session.tool_catalog.remote_name_by_model_name == {
                "browser_click": "browser_click"
            }

    asyncio.run(exercise())

    assert observed == ["http://browser.test/mcp", "enter", "list", "exit"]
