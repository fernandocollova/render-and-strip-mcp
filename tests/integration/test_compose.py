"""Tests for the real Docker Compose dependency stack."""

from __future__ import annotations

import asyncio
import json
from urllib.parse import urljoin
from urllib.request import urlopen

import pytest
from fastmcp import Client

from render_and_strip_mcp.browser_tabs import (
    current_tab_index,
    list_browser_tabs,
    select_original_tab,
)
from render_and_strip_mcp.html_cleaner import clean_rendered_html
from render_and_strip_mcp.mcp_results import extract_json_string_result, extract_text_result
from render_and_strip_mcp.playwright_tools import open_playwright_session
from render_and_strip_mcp.rendered_document import fetch_visible_top_level_document


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
def test_compose_mcp_cleans_fixture_end_to_end(
    compose_application_endpoint: str,
    compose_fixture_url: str,
) -> None:
    """The public MCP tool and built-in model complete a fixture page-cleaning request."""

    expected_cleaned_html = (
        "<!doctype html>\n"
        '<html><head><meta charset="utf-8"/></head><body>\n'
        "<header>Fixture chrome</header>\n"
        "<main>\n"
        "<h1>Deterministic fixture page</h1>\n"
        "<p>This text verifies rendered semantic HTML cleanup.</p>\n"
        f'<a href="{urljoin(compose_fixture_url, "details.html")}">Fixture details</a>\n'
        "</main>\n"
        "<footer>Fixture footer</footer>\n"
        "</body></html>"
    )

    async def exercise() -> str:
        async with Client(compose_application_endpoint) as client:
            result = await client.call_tool(
                "render_and_strip_page",
                {
                    "url": compose_fixture_url,
                    "task": "Clean the current page.",
                },
            )
        return extract_text_result(result)

    assert asyncio.run(exercise()) == expected_cleaned_html


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
                document_html = await fetch_visible_top_level_document(session.client, 5)
                return clean_rendered_html(document_html, compose_fixture_url, True, 0)
            finally:
                close_result = await session.client.call_tool("browser_close", {}, timeout=5)
                extract_text_result(close_result)

    cleaned_html = asyncio.run(exercise())

    assert "Deterministic fixture page" in cleaned_html
    assert "Fixture chrome" in cleaned_html
    assert "Fixture footer" in cleaned_html
    assert f'href="{urljoin(compose_fixture_url, "details.html")}"' in cleaned_html
