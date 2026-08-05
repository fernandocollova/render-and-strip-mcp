"""Deterministic semantic cleanup of a rendered top-level HTML document."""

from __future__ import annotations

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from .errors import BrowserAgentError
from .html_elements import ALLOWED_TAGS, REMOVED_TAGS
from .link_destination import sanitize_link_destination


def clean_rendered_html(
    document_html: str,
    final_url: str,
    allow_plain_http: bool,
    maximum_html_bytes: int,
) -> str:
    """Return a complete semantic document or fail when the configured output cap is exceeded."""

    source_document = BeautifulSoup(document_html, "html.parser")
    document_title = _document_title(source_document)
    for comment in source_document.find_all(string=lambda value: isinstance(value, Comment)):
        comment.extract()
    for image in source_document.find_all("img"):
        alternative_text = image.get("alt")
        if isinstance(alternative_text, str) and alternative_text.strip():
            image.replace_with(NavigableString(f"[Image: {alternative_text.strip()}]"))
        else:
            image.decompose()
    if source_document.head is not None:
        source_document.head.decompose()
    source_body = source_document.body or source_document
    _remove_nontext_content(source_body)
    _clean_semantic_tags(source_body, final_url, allow_plain_http)
    cleaned_html = _serialize_document(source_body, document_title)
    if maximum_html_bytes and len(cleaned_html.encode("utf-8")) > maximum_html_bytes:
        raise BrowserAgentError("Clean HTML exceeds the configured UTF-8 byte limit.")
    return cleaned_html


def _document_title(document: BeautifulSoup) -> str:
    """Extract a textual input title before the source head is removed."""

    if document.head is None:
        return ""
    title_tag = document.head.find("title", recursive=False)
    if title_tag is None:
        return ""
    return title_tag.get_text(" ", strip=True)


def _remove_nontext_content(source_body: Tag | BeautifulSoup) -> None:
    """Remove content that cannot be represented in safe text-only HTML."""

    for tag in list(source_body.find_all(REMOVED_TAGS)):
        tag.decompose()


def _clean_semantic_tags(
    source_body: Tag | BeautifulSoup,
    final_url: str,
    allow_plain_http: bool,
) -> None:
    """Unwrap layout markup and reduce retained semantic elements to allowed attributes."""

    for tag in list(source_body.find_all(True)):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue
        _clean_attributes(tag, final_url, allow_plain_http)


def _clean_attributes(tag: Tag, final_url: str, allow_plain_http: bool) -> None:
    """Preserve only element-specific allowed attributes and sanitize link destinations."""

    attributes: dict[str, str] = {}
    if tag.name == "a":
        readable_text = tag.get_text(" ", strip=True)
        aria_label = tag.get("aria-label")
        if not readable_text and isinstance(aria_label, str) and aria_label.strip():
            tag.clear()
            tag.append(NavigableString(aria_label.strip()))
        href = sanitize_link_destination(tag.get("href"), final_url, allow_plain_http)
        if href is not None:
            attributes["href"] = href
        _copy_string_attribute(tag, attributes, "title")
    elif tag.name in {"th", "td"}:
        for attribute_name in ("colspan", "rowspan", "scope"):
            _copy_string_attribute(tag, attributes, attribute_name)
    elif tag.name == "time":
        _copy_string_attribute(tag, attributes, "datetime")
    elif tag.name == "abbr":
        _copy_string_attribute(tag, attributes, "title")
    tag.attrs = attributes


def _copy_string_attribute(tag: Tag, target: dict[str, str], attribute_name: str) -> None:
    """Copy an allowed string attribute without retaining arbitrary source attributes."""

    value = tag.get(attribute_name)
    if isinstance(value, str):
        target[attribute_name] = value


def _serialize_document(source_body: Tag | BeautifulSoup, title: str) -> str:
    """Serialize the fixed UTF-8 HTML skeleton with cleaned top-level body content."""

    output_document = BeautifulSoup("", "html.parser")
    html = output_document.new_tag("html")
    head = output_document.new_tag("head")
    meta = output_document.new_tag("meta", charset="utf-8")
    head.append(meta)
    if title:
        title_tag = output_document.new_tag("title")
        title_tag.string = title
        head.append(title_tag)
    body = output_document.new_tag("body")
    for child in list(source_body.contents):
        body.append(child.extract())
    html.append(head)
    html.append(body)
    return f"<!doctype html>\n{html}"
