"""Tests for source-aware cleaning and ordered selected-content assembly."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from render_and_strip_mcp.errors import BrowserAgentError
from render_and_strip_mcp.html_cleaner import normalize_captured_content
from render_and_strip_mcp.selected_content import CapturedContent


def test_one_and_many_captures_use_the_same_fixed_shape() -> None:
    """Every strategy receives one skeleton and exactly one application-owned main."""

    first = CapturedContent(
        '<main><article><h1>First</h1><a href="notes">Notes</a></article></main>',
        "https://example.test/releases/1/",
    )
    second = CapturedContent(
        "<div><ul><li>Second</li></ul><table><tr><td>Value</td></tr></table></div>",
        "https://example.test/releases/2/",
    )

    one_result = normalize_captured_content([first], False, 0)
    many_result = normalize_captured_content([first, second], False, 0)

    for result in (one_result, many_result):
        parsed = BeautifulSoup(result, "html.parser")
        assert result.startswith('<!doctype html>\n<html><head><meta charset="utf-8"/>')
        assert len(parsed.find_all("main")) == 1
        assert parsed.body is not None
        assert [tag.name for tag in parsed.body.find_all(recursive=False)] == ["main"]
        assert parsed.find(attrs={"class": True}) is None
    assert "Second" not in one_result
    assert many_result.index("First") < many_result.index("Second")
    assert "<section>" not in many_result
    assert "<article>" in many_result
    assert "<ul>" in many_result and "<table>" in many_result


def test_each_region_resolves_links_against_its_own_source_url() -> None:
    """Independent cleaning retains the source URL associated with each capture."""

    captures = [
        CapturedContent('<article><a href="notes">One</a></article>', "https://a.test/1/"),
        CapturedContent('<article><a href="notes">Two</a></article>', "https://b.test/2/"),
    ]

    parsed = BeautifulSoup(normalize_captured_content(captures, False, 0), "html.parser")

    assert [link["href"] for link in parsed.find_all("a")] == [
        "https://a.test/1/notes",
        "https://b.test/2/notes",
    ]


def test_aggregate_utf8_limit_applies_after_complete_assembly() -> None:
    """The byte cap measures the fixed wrapper and all regions without truncation."""

    captures = [
        CapturedContent("<p>First café</p>", "https://example.test/1"),
        CapturedContent("<p>Second ☕</p>", "https://example.test/2"),
    ]
    unlimited_result = normalize_captured_content(captures, False, 0)
    exact_size = len(unlimited_result.encode("utf-8"))

    assert normalize_captured_content(captures, False, exact_size) == unlimited_result
    with pytest.raises(BrowserAgentError, match="UTF-8 byte limit"):
        normalize_captured_content(captures, False, exact_size - 1)


def test_assembly_rejects_missing_captured_content() -> None:
    """A completed strategy cannot turn an empty capture list into empty HTML."""

    with pytest.raises(BrowserAgentError, match="without captured content"):
        normalize_captured_content([], False, 0)
