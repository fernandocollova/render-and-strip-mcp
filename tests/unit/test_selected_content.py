"""Tests for strict targeted selected-content retrieval from browser_evaluate."""

from __future__ import annotations

import asyncio

import pytest
from fastmcp.client.client import CallToolResult
from mcp.types import TextContent

from render_and_strip_mcp.errors import BrowserAgentError
from render_and_strip_mcp.selected_content import (
    VISIBLE_SELECTED_REGION_EXPRESSION,
    fetch_visible_selected_region,
)
from render_and_strip_mcp.stage_models import SelectedRegion


class FakeBrowserClient:
    """Minimal client returning one prescribed targeted evaluation result."""

    def __init__(self, result: CallToolResult):
        self.result = result
        self.arguments: dict[str, object] | None = None

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, object],
        **kwargs: object,
    ) -> CallToolResult:
        assert name == "browser_evaluate"
        self.arguments = arguments
        return self.result


def evaluation_result(text: str, is_error: bool = False) -> CallToolResult:
    """Return a textual official-MCP browser_evaluate response."""

    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=None,
        meta=None,
        is_error=is_error,
    )


def test_fetch_visible_region_uses_pinned_targeted_contract() -> None:
    """Capture passes the fresh description and target with the exact clone expression."""

    client = FakeBrowserClient(evaluation_result('### Result\n"<article>Visible</article>"'))
    selection = SelectedRegion(element="Release article", target="e42")

    region = asyncio.run(fetch_visible_selected_region(client, selection, 1))  # type: ignore[arg-type]

    assert region == "<article>Visible</article>"
    assert client.arguments == {
        "function": VISIBLE_SELECTED_REGION_EXPRESSION,
        "element": "Release article",
        "target": "e42",
    }


@pytest.mark.parametrize(
    "result",
    [
        evaluation_result("### Error\nstale target", is_error=True),
        evaluation_result('### Result\n"<div>unclosed"'),
        evaluation_result('### Result\n"<body>full fallback</body>"'),
        evaluation_result('### Result\n"<article>one</article><article>two</article>"'),
        evaluation_result("### Result\nnull"),
    ],
)
def test_fetch_visible_region_rejects_stale_missing_or_malformed_selection(
    result: CallToolResult,
) -> None:
    """Target failures and non-subtree results fail without any body fallback."""

    with pytest.raises(BrowserAgentError):
        asyncio.run(
            fetch_visible_selected_region(  # type: ignore[arg-type]
                FakeBrowserClient(result),
                SelectedRegion(element="Release article", target="e42"),
                1,
            )
        )


def test_visibility_expression_filters_selected_subtree_without_shadow_or_body_fallback() -> None:
    """The targeted clone retains all documented visibility predicates."""

    for required_fragment in (
        "selectedElement instanceof Element",
        "cloneVisibleNode(selectedElement)",
        "element.hidden",
        "aria-hidden",
        "TEMPLATE",
        "inert",
        "display === 'none'",
        "visibility === 'hidden'",
        "visibility === 'collapse'",
        "contentVisibility === 'hidden'",
        "style.opacity",
        "DETAILS",
    ):
        assert required_fragment in VISIBLE_SELECTED_REGION_EXPRESSION
    assert "document.body" not in VISIBLE_SELECTED_REGION_EXPRESSION
    assert "document.documentElement" not in VISIBLE_SELECTED_REGION_EXPRESSION
    assert "shadowRoot" not in VISIBLE_SELECTED_REGION_EXPRESSION
