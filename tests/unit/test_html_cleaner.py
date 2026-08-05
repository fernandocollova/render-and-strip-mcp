"""Fixtures for semantic HTML cleaning and safe-link policy."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from render_and_strip_mcp.errors import BrowserAgentError
from render_and_strip_mcp.html_cleaner import clean_rendered_html
from render_and_strip_mcp.rendered_document import VISIBLE_DOCUMENT_EXPRESSION


def clean(source: str, *, allow_plain_http: bool = False, maximum_html_bytes: int = 0) -> str:
    """Clean source HTML against one stable final page URL."""

    return clean_rendered_html(
        source,
        "https://example.test/path/page",
        allow_plain_http,
        maximum_html_bytes,
    )


def test_cleaner_preserves_semantics_and_visible_page_regions() -> None:
    """Allowed visible semantics and landmarks survive without source attributes."""

    result = clean(
        """
<html><head><title> Example title </title><style>.x { color: red }</style></head>
<body><header class="global">Global header</header><nav id="navigation">Navigation</nav>
<aside data-content="supplemental">Aside</aside><div role="contentinfo">Role landmark</div>
<main class="layout"><header>Inside header</header><article id="content">
<h1 onclick="bad()">Heading</h1>
<p style="color:red">Paragraph <strong>text</strong>.</p><table><tr><th scope="col">A</th>
<td colspan="2" rowspan="1" data-value="x">B</td></tr></table>
<time datetime="2026-01-01">Today</time>
<abbr title="HyperText Markup Language">HTML</abbr></article><footer>Inside footer</footer></main>
<footer class="global">Global footer</footer><script>alert(1)</script>
</body></html>
"""
    )
    document = BeautifulSoup(result, "html.parser")

    assert result.startswith("<!doctype html>\n<html>")
    assert document.title is not None and document.title.string == "Example title"
    assert "Global header" in result
    assert "Navigation" in result
    assert "Aside" in result
    assert "Role landmark" in result
    assert "Global footer" in result
    assert "Inside header" in result
    assert "Inside footer" in result
    assert document.header is not None and document.header.attrs == {}
    assert document.nav is not None and document.nav.attrs == {}
    assert document.aside is not None and document.aside.attrs == {}
    assert document.footer is not None and document.footer.attrs == {}
    assert document.find("div") is None
    assert document.h1 is not None and document.h1.attrs == {}
    assert document.td is not None and document.td.attrs == {"colspan": "2", "rowspan": "1"}
    assert document.th is not None and document.th.attrs == {"scope": "col"}
    assert document.time is not None and document.time.attrs == {"datetime": "2026-01-01"}
    assert document.abbr is not None
    assert document.abbr.attrs == {"title": "HyperText Markup Language"}


def test_cleaner_converts_picture_image_text_and_excludes_embedded_content() -> None:
    """Picture alternative text survives, while iframe and template content do not."""

    result = clean(
        """
<html><body><main><p>Before <picture><source srcset="chart.webp"><img alt="A chart">
</picture> after <img alt=""></p>
<iframe srcdoc="<p>iframe secret</p>">fallback</iframe>
<template shadowrootmode="open"><p>shadow secret</p></template></main></body></html>
"""
    )

    assert "[Image: A chart]" in result
    assert "iframe secret" not in result
    assert "fallback" not in result
    assert "shadow secret" not in result
    assert "<img" not in result


def test_cleaner_retains_form_text_but_excludes_form_state_and_nontext_content() -> None:
    """Text-bearing form containers unwrap while controls and unsafe content are removed."""

    result = clean(
        """
<html><body><main><form action="/send"><fieldset><legend>Contact us</legend>
<label for="email">Email address <input id="email" value="secret@example.test"></label>
<button onclick="submit()">Send message</button><output>Form ready</output>
<textarea>Unsent private message</textarea><select><option>United Kingdom</option></select>
<datalist><option>Suggestion</option></datalist></fieldset></form>
<dialog open>Contact confirmation</dialog><script>script secret</script>
<video>Video fallback</video><svg><title>Chart title</title></svg>
<iframe srcdoc="<p>iframe secret</p>">iframe fallback</iframe>
<template><p>template secret</p></template></main></body></html>
"""
    )
    document = BeautifulSoup(result, "html.parser")

    for expected_text in (
        "Contact us",
        "Email address",
        "Send message",
        "Form ready",
        "Contact confirmation",
    ):
        assert expected_text in result
    for excluded_text in (
        "secret@example.test",
        "Unsent private message",
        "United Kingdom",
        "Suggestion",
        "script secret",
        "Video fallback",
        "Chart title",
        "iframe secret",
        "iframe fallback",
        "template secret",
    ):
        assert excluded_text not in result
    for tag_name in (
        "form",
        "fieldset",
        "legend",
        "label",
        "button",
        "output",
        "dialog",
        "input",
        "textarea",
        "select",
        "option",
    ):
        assert document.find(tag_name) is None


@pytest.mark.parametrize(
    ("href", "allow_plain_http", "expected_href"),
    [
        ("/next", False, "https://example.test/next"),
        ("#section", False, "#section"),
        ("https://other.test/page", False, "https://other.test/page"),
        ("mailto:person@example.test", False, "mailto:person@example.test"),
        ("tel:+12025550123", False, "tel:+12025550123"),
        ("http://other.test/page", False, None),
        ("http://other.test/page", True, "http://other.test/page"),
        ("javascript:alert(1)", False, None),
        ("data:text/plain,unsafe", False, None),
        ("file:///tmp/private", False, None),
        ("blob:https://example.test/id", False, None),
        ("https://user:password@example.test/", False, None),
    ],
)
def test_link_policy_sanitizes_resolved_destinations(
    href: str,
    allow_plain_http: bool,
    expected_href: str | None,
) -> None:
    """Link schemes, credentials, and HTTP policy are enforced without losing readable text."""

    source = f'<html><body><a href="{href}">Read</a></body></html>'
    document = BeautifulSoup(clean(source, allow_plain_http=allow_plain_http), "html.parser")

    assert document.a is not None
    assert document.a.get_text() == "Read"
    assert document.a.get("href") == expected_href


def test_link_aria_label_becomes_text_and_all_unknown_markup_is_unwrapped() -> None:
    """An inaccessible link receives readable label text and generic layout retains text."""

    document = BeautifulSoup(
        clean('<html><body><div><a href="/next" aria-label="Next page"></a></div></body></html>'),
        "html.parser",
    )

    assert document.a is not None
    assert document.a.get_text() == "Next page"
    assert document.a.attrs == {"href": "https://example.test/next"}
    assert document.div is None


def test_cleaner_handles_malformed_fragment_and_rejects_output_overage() -> None:
    """Malformed input is normalized, while byte limits fail without truncating a document."""

    result = clean("<div><p>Unclosed")

    assert "<p>Unclosed</p>" in result
    with pytest.raises(BrowserAgentError, match="byte limit"):
        clean("<html><body><p>Long document</p></body></html>", maximum_html_bytes=10)


def test_visibility_expression_contains_all_documented_predicates() -> None:
    """The pinned browser expression filters only the requested top-level hidden conditions."""

    for required_fragment in (
        "document.documentElement",
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
        assert required_fragment in VISIBLE_DOCUMENT_EXPRESSION
    assert "shadowRoot" not in VISIBLE_DOCUMENT_EXPRESSION
