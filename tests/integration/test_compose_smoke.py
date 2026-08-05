"""Opt-in smoke test for the started Docker Compose browser dependencies."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from urllib.request import urlopen

import pytest
from fastmcp import Client

from render_and_strip_mcp.config import load_settings
from render_and_strip_mcp.mcp_results import extract_json_string_result


@pytest.mark.integration
def test_compose_browser_and_plain_http_fixture() -> None:
    """Navigate an isolated Playwright session to the explicitly enabled fixture site."""

    if os.environ.get("RUN_COMPOSE_SMOKE") != "1":
        pytest.skip("set RUN_COMPOSE_SMOKE=1 after starting Docker Compose")
    settings = load_settings(Path("examples/compose.toml"))
    assert settings.agent.allow_plain_http is True
    with urlopen("http://localhost:8081/", timeout=5) as response:
        assert b"Deterministic fixture page" in response.read()

    async def exercise() -> None:
        async with Client(str(settings.playwright_mcp.endpoint)) as client:
            tool_names = {tool.name for tool in await client.list_tools()}
            assert {
                "browser_navigate",
                "browser_tabs",
                "browser_evaluate",
                "browser_close",
            } <= tool_names
            try:
                await client.call_tool("browser_navigate", {"url": "http://test-site:8081/"})
                location_result = await client.call_tool(
                    "browser_evaluate",
                    {"function": "() => location.href"},
                )
                assert extract_json_string_result(location_result) == "http://test-site:8081/"
            finally:
                await client.call_tool("browser_close", {})

    asyncio.run(exercise())
