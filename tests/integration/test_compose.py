"""Tests for the real Docker Compose dependency stack."""

from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import urljoin
from urllib.request import urlopen

import pytest
from fastmcp import Client

from render_and_strip_mcp.browser_tabs import (
    current_tab_index,
    list_browser_tabs,
    select_original_tab,
)
from render_and_strip_mcp.html_cleaner import clean_selected_region
from render_and_strip_mcp.mcp_results import extract_json_string_result, extract_text_result
from render_and_strip_mcp.playwright_tools import open_playwright_session
from render_and_strip_mcp.selected_content import fetch_visible_selected_region
from render_and_strip_mcp.stage_models import SelectedRegion


@pytest.mark.integration
def test_compose_exposes_fixture_model_and_application_transports(
    compose_application_endpoint: str,
    compose_fixture_url: str,
    compose_model_catalog_url: str,
) -> None:
    """The real fixture, OpenAI-compatible model, and public MCP server are reachable."""

    with urlopen(compose_fixture_url, timeout=5) as response:
        assert b"Deterministic fixture page" in response.read()
    with urlopen(compose_model_catalog_url, timeout=5) as response:
        model_catalog = json.load(response)
    assert model_catalog["object"] == "list"
    assert model_catalog["data"]

    async def exercise() -> None:
        async with Client(compose_application_endpoint) as client:
            tools = await client.list_tools()
        assert [tool.name for tool in tools] == ["render_and_strip_page"]

    asyncio.run(exercise())


@pytest.mark.integration
def test_compose_playwright_session_renders_and_cleans_fixture(
    compose_fixture_url: str,
    compose_playwright_endpoint: str,
) -> None:
    """Real Playwright MCP responses work with the application's session and render helpers."""

    async def exercise() -> str:
        async with open_playwright_session(compose_playwright_endpoint) as session:
            assert {"browser_navigate", "browser_evaluate"} <= set(
                session.tool_catalog.remote_name_by_model_name
            )
            try:
                navigation = await session.client.call_tool(
                    "browser_navigate",
                    {"url": compose_fixture_url},
                    timeout=5,
                )
                assert "Deterministic fixture" in extract_text_result(navigation)
                tabs = await list_browser_tabs(session.client, 5)
                original_tab_index = current_tab_index(tabs)
                selected_tab = await select_original_tab(session.client, original_tab_index, 5)
                assert selected_tab.is_current is True
                location_result = await session.client.call_tool(
                    "browser_evaluate",
                    {"function": "() => location.href"},
                    timeout=5,
                )
                assert extract_json_string_result(location_result) == compose_fixture_url
                snapshot = extract_text_result(
                    await session.client.call_tool("browser_snapshot", {}, timeout=5)
                )
                main_target = re.search(r"main \[ref=([^\]]+)\]", snapshot)
                assert main_target is not None
                region_html = await fetch_visible_selected_region(
                    session.client,
                    SelectedRegion(
                        element="Deterministic fixture main content",
                        target=main_target.group(1),
                    ),
                    5,
                )
                return clean_selected_region(region_html, compose_fixture_url, True)
            finally:
                close_result = await session.client.call_tool("browser_close", {}, timeout=5)
                extract_text_result(close_result)

    cleaned_html = asyncio.run(exercise())

    assert "Deterministic fixture page" in cleaned_html
    assert "Fixture chrome" not in cleaned_html
    assert "Fixture navigation" not in cleaned_html
    assert "Fixture sidebar" not in cleaned_html
    assert "Fixture footer" not in cleaned_html
    assert f'href="{urljoin(compose_fixture_url, "details.html")}"' in cleaned_html


@pytest.mark.integration
def test_compose_fresh_snapshots_observe_retained_lazy_content(
    compose_fixture_url: str,
    compose_playwright_endpoint: str,
) -> None:
    """Real snapshots and semantic waits retain deterministic expanded fixture content."""

    greedy_fixture_url = urljoin(compose_fixture_url, "greedy.html")

    async def exercise() -> tuple[str, str, str]:
        async with open_playwright_session(compose_playwright_endpoint) as session:
            try:
                navigation = await session.client.call_tool(
                    "browser_navigate", {"url": greedy_fixture_url}, timeout=5
                )
                extract_text_result(navigation)
                before_snapshot = await session.client.call_tool("browser_snapshot", {}, timeout=5)
                await session.client.call_tool(
                    "browser_evaluate",
                    {
                        "function": (
                            "() => { document.querySelector('#load-more').click(); "
                            "return 'triggered'; }"
                        )
                    },
                    timeout=5,
                )
                wait_result = await session.client.call_tool(
                    "browser_wait_for", {"text": "Lazy retained item."}, timeout=5
                )
                extract_text_result(wait_result)
                after_snapshot = await session.client.call_tool("browser_snapshot", {}, timeout=5)
                after_snapshot_text = extract_text_result(after_snapshot)
                main_target = re.search(r"main \[ref=([^\]]+)\]", after_snapshot_text)
                assert main_target is not None
                region_html = await fetch_visible_selected_region(
                    session.client,
                    SelectedRegion(
                        element="Greedy fixture main content",
                        target=main_target.group(1),
                    ),
                    5,
                )
                return (
                    extract_text_result(before_snapshot),
                    after_snapshot_text,
                    region_html,
                )
            finally:
                close_result = await session.client.call_tool("browser_close", {}, timeout=5)
                extract_text_result(close_result)

    before_snapshot, after_snapshot, region_html = asyncio.run(exercise())

    assert "Lazy retained item." not in before_snapshot
    assert "Lazy retained item." in after_snapshot
    assert "Lazy retained item." in region_html
