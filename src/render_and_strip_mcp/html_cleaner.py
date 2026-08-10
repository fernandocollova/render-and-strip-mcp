"""Source-aware semantic cleanup and uniform assembly of selected content."""

from __future__ import annotations

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from .errors import BrowserAgentError
from .html_elements import ALLOWED_TAGS, REMOVED_TAGS
from .link_destination import sanitize_link_destination
from .selected_content import CapturedContent


def clean_selected_region(
    region_html: str,
    source_url: str,
    allow_plain_http: bool,
) -> str:
    """Independently normalize one selected region against its source URL."""

    source_region = BeautifulSoup(region_html, "html.parser")
    for comment in source_region.find_all(string=lambda value: isinstance(value, Comment)):
        comment.extract()
    for image in source_region.find_all("img"):
        alternative_text = image.get("alt")
        if isinstance(alternative_text, str) and alternative_text.strip():
            image.replace_with(NavigableString(f"[Image: {alternative_text.strip()}]"))
        else:
            image.decompose()
    _remove_nontext_content(source_region)
    _clean_semantic_tags(source_region, source_url, allow_plain_http)
    return _serialize_document(source_region)


def normalize_captured_content(
    captured_content: list[CapturedContent],
    allow_plain_http: bool,
    maximum_html_bytes: int,
) -> str:
    """Clean and assemble all selected regions under one main in capture order."""

    if not captured_content:
        raise BrowserAgentError("Collection completed without captured content.")

    assembled_content = BeautifulSoup("", "html.parser")
    for capture in captured_content:
        cleaned_region = BeautifulSoup(
            clean_selected_region(capture.html, capture.source_url, allow_plain_http),
            "html.parser",
        )
        for child in list(cleaned_region.main.contents):
            assembled_content.append(child.extract())

    assembled_html = _serialize_document(assembled_content)
    _enforce_output_limit(assembled_html, maximum_html_bytes)
    return assembled_html


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
        if tag.name == "main" or tag.name not in ALLOWED_TAGS:
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


def _serialize_document(source_content: Tag | BeautifulSoup) -> str:
    """Serialize the fixed UTF-8 HTML skeleton with one application-owned main."""

    output_document = BeautifulSoup("", "html.parser")
    html = output_document.new_tag("html")
    head = output_document.new_tag("head")
    meta = output_document.new_tag("meta", charset="utf-8")
    head.append(meta)
    body = output_document.new_tag("body")
    main = output_document.new_tag("main")
    for child in list(source_content.contents):
        main.append(child.extract())
    body.append(main)
    html.append(head)
    html.append(body)
    return f"<!doctype html>\n{html}"


def _enforce_output_limit(cleaned_html: str, maximum_html_bytes: int) -> None:
    """Reject a complete UTF-8 result that exceeds the configured aggregate cap."""

    if maximum_html_bytes and len(cleaned_html.encode("utf-8")) > maximum_html_bytes:
        raise BrowserAgentError("Clean HTML exceeds the configured UTF-8 byte limit.")
