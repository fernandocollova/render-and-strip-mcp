"""Tests for strict final-document retrieval from browser_evaluate."""

from __future__ import annotations

import asyncio

import pytest
from mcp.types import CallToolResult, TextContent

from render_and_strip_mcp.errors import BrowserAgentError
from render_and_strip_mcp.rendered_document import (
    VISIBLE_DOCUMENT_EXPRESSION,
    fetch_visible_top_level_document,
)


class FakeBrowserClient:
    """Minimal client returning one prescribed browser_evaluate result."""

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

    return CallToolResult(content=[TextContent(type="text", text=text)], isError=is_error)


def test_fetch_visible_document_uses_pinned_expression() -> None:
    """Final DOM retrieval sends the exact configured clone expression and reads JSON text."""

    client = FakeBrowserClient(
        evaluation_result('### Result\n"<html><head></head><body><p>Visible</p></body></html>"')
    )

    document = asyncio.run(fetch_visible_top_level_document(client, 1))  # type: ignore[arg-type]

    assert document == "<html><head></head><body><p>Visible</p></body></html>"
    assert client.arguments == {"function": VISIBLE_DOCUMENT_EXPRESSION}


@pytest.mark.parametrize(
    "result",
    [
        evaluation_result("### Error\nremote failure", is_error=True),
        evaluation_result('### Result\n"<div>not a document</div>"'),
        evaluation_result("### Result\nundefined"),
    ],
)
def test_fetch_visible_document_rejects_remote_missing_or_malformed_text(
    result: CallToolResult,
) -> None:
    """Remote errors, non-JSON results, and non-document HTML have no partial fallback."""

    with pytest.raises(BrowserAgentError):
        asyncio.run(fetch_visible_top_level_document(FakeBrowserClient(result), 1))  # type: ignore[arg-type]
