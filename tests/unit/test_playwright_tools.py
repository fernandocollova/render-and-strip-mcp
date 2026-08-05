"""Tests for the tested official Playwright MCP tool contract."""

from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest
from mcp.types import Tool

import render_and_strip_mcp.playwright_tools as playwright_tools
from render_and_strip_mcp.errors import BrowserCompatibilityError, ToolSchemaError
from render_and_strip_mcp.playwright_contract import (
    OFFICIAL_PLAYWRIGHT_MCP_HTTP_PATH,
    OFFICIAL_PLAYWRIGHT_MCP_VERSION,
    OFFICIAL_REQUIRED_TOOL_SCHEMAS,
)


def official_tools() -> list[Tool]:
    """Return the minimum official tools plus representative eligible actions."""

    return [
        *[
            Tool(name=name, description=f"Official {name}", inputSchema=deepcopy(schema))
            for name, schema in OFFICIAL_REQUIRED_TOOL_SCHEMAS.items()
        ],
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


def test_required_capabilities_validate_documented_shapes() -> None:
    """The official navigation, tabs, evaluation, and close tools are required."""

    playwright_tools.validate_required_capabilities(official_tools())

    incomplete_tools = [tool for tool in official_tools() if tool.name != "browser_close"]
    with pytest.raises(BrowserCompatibilityError, match="browser_close"):
        playwright_tools.validate_required_capabilities(incomplete_tools)

    malformed_tools = official_tools()
    malformed_tools[0] = Tool(
        name="browser_navigate",
        description="Navigate",
        inputSchema=object_schema("target"),
    )
    with pytest.raises(BrowserCompatibilityError, match="incompatible input properties"):
        playwright_tools.validate_required_capabilities(malformed_tools)


def test_pinned_official_contract_records_endpoint_and_required_schemas() -> None:
    """Compatibility metadata records the exact upstream interface this service supports."""

    assert OFFICIAL_PLAYWRIGHT_MCP_VERSION == "0.0.78"
    assert OFFICIAL_PLAYWRIGHT_MCP_HTTP_PATH == "/mcp"
    assert OFFICIAL_REQUIRED_TOOL_SCHEMAS == {
        "browser_navigate": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        "browser_tabs": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "new", "close", "select"]},
                "index": {"type": "number"},
                "url": {"type": "string"},
            },
            "required": ["action"],
        },
        "browser_evaluate": {
            "type": "object",
            "properties": {
                "function": {"type": "string"},
                "element": {"type": "string"},
                "target": {"type": "string"},
                "filename": {"type": "string"},
            },
            "required": ["function"],
        },
        "browser_close": {"type": "object", "properties": {}, "required": []},
    }


def test_catalog_excludes_reserved_and_unsafe_tools() -> None:
    """Only eligible browser actions are exposed as callable model tools."""

    catalog = playwright_tools.build_tool_catalog(official_tools())

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


def test_catalog_rejects_invalid_openai_tool_name() -> None:
    """An incompatible remote tool name fails instead of receiving a compatibility mapping."""

    tools = [*official_tools(), Tool(name="browser action", inputSchema=object_schema())]

    with pytest.raises(ToolSchemaError, match="invalid OpenAI function name"):
        playwright_tools.build_tool_catalog(tools)


def test_catalog_rejects_missing_tool_description() -> None:
    """Eligible tools must retain the official interface's non-empty description."""

    tools = [*official_tools(), Tool(name="browser_custom", inputSchema=object_schema())]

    with pytest.raises(ToolSchemaError, match="must have a description"):
        playwright_tools.build_tool_catalog(tools)


def test_catalog_rejects_nonportable_schema_keywords() -> None:
    """Unsupported schema semantics fail rather than being silently omitted."""

    tools = [
        *official_tools(),
        Tool(
            name="browser_custom",
            inputSchema={"type": "object", "properties": {}, "oneOf": []},
        ),
    ]

    with pytest.raises(ToolSchemaError, match="oneOf"):
        playwright_tools.build_tool_catalog(tools)


def test_open_session_discovers_and_validates_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each opener creates one async client session and exposes its catalog."""

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
            return official_tools()

    monkeypatch.setattr(playwright_tools, "Client", FakeClient)

    async def exercise() -> None:
        async with playwright_tools.open_playwright_session("http://browser.test/mcp") as session:
            assert "browser_click" in session.tool_catalog.remote_name_by_model_name

    asyncio.run(exercise())

    assert observed == ["http://browser.test/mcp", "enter", "list", "exit"]
