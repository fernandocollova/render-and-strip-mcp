"""Tests for source-aware cleaning and ordered rendered-document assembly."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from render_and_strip_mcp.errors import BrowserAgentError
from render_and_strip_mcp.html_cleaner import clean_rendered_documents, clean_rendered_html
from render_and_strip_mcp.rendered_document import RenderedDocument


def test_single_rendered_document_preserves_exact_cleaner_output() -> None:
    """The existing one-document path remains byte-for-byte compatible."""

    document = RenderedDocument(
        html=(
            "<html><head><title>One page</title></head><body>"
            '<main><h1>Release</h1><a href="notes">Notes</a></main></body></html>'
        ),
        source_url="https://example.test/releases/1/",
    )

    assert clean_rendered_documents([document], False, 0) == clean_rendered_html(
        document.html,
        document.source_url,
        False,
        0,
    )


def test_multiple_documents_resolve_links_per_source_and_preserve_order() -> None:
    """Each complete cleaned body keeps its own link base and ordered section."""

    documents = [
        RenderedDocument(
            '<html><body><article><h2>First</h2><a href="notes">Notes one</a>'
            "</article></body></html>",
            "https://example.test/releases/page/1/",
        ),
        RenderedDocument(
            '<html><body><article><h2>Second</h2><a href="notes">Notes two</a>'
            "</article></body></html>",
            "https://example.test/archive/page/2/",
        ),
    ]

    result = clean_rendered_documents(documents, False, 0)
    parsed = BeautifulSoup(result, "html.parser")
    sections = parsed.body.find_all("section", recursive=False)

    assert result.startswith('<!doctype html>\n<html><head><meta charset="utf-8"/>')
    assert [section.get_text(" ", strip=True) for section in sections] == [
        "First Notes one",
        "Second Notes two",
    ]
    assert [link["href"] for link in parsed.find_all("a")] == [
        "https://example.test/releases/page/1/notes",
        "https://example.test/archive/page/2/notes",
    ]
    assert result.index("First") < result.index("Second")


def test_aggregate_utf8_limit_applies_after_complete_assembly() -> None:
    """The byte cap measures the final wrapper and all cleaned bodies without truncation."""

    documents = [
        RenderedDocument(
            "<html><body><p>First café</p></body></html>",
            "https://example.test/1",
        ),
        RenderedDocument(
            "<html><body><p>Second ☕</p></body></html>",
            "https://example.test/2",
        ),
    ]
    unlimited_result = clean_rendered_documents(documents, False, 0)
    exact_size = len(unlimited_result.encode("utf-8"))

    assert clean_rendered_documents(documents, False, exact_size) == unlimited_result
    with pytest.raises(BrowserAgentError, match="UTF-8 byte limit"):
        clean_rendered_documents(documents, False, exact_size - 1)


def test_assembly_rejects_missing_captured_documents() -> None:
    """A completed strategy cannot turn an internal empty capture into empty HTML."""

    with pytest.raises(BrowserAgentError, match="without a rendered document"):
        clean_rendered_documents([], False, 0)
