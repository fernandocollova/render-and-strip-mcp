"""Strict parsing of the pinned official Playwright MCP textual results."""

from __future__ import annotations

import json
import re

from fastmcp.client.client import CallToolResult
from mcp.types import TextContent

from .errors import BrowserAgentError

RESULT_SECTION = re.compile(r"^### Result\n(?P<result>.*?)(?=^### |\Z)", re.MULTILINE | re.DOTALL)


def extract_text_result(result: CallToolResult) -> str:
    """Return the official server's textual response or fail on a remote error result."""

    if result.is_error:
        raise BrowserAgentError(_error_message(result))
    content = result.content
    has_only_text_content = content and all(
        isinstance(content_item, TextContent) for content_item in content
    )
    if not has_only_text_content:
        raise BrowserAgentError("Playwright MCP returned missing or non-text result content.")
    return "\n".join(content_item.text for content_item in content)


def extract_json_string_result(result: CallToolResult) -> str:
    """Decode a string returned by browser_evaluate's documented Result section."""

    text_result = extract_text_result(result)
    result_match = RESULT_SECTION.search(text_result)
    if result_match is None:
        raise BrowserAgentError("Playwright browser_evaluate response has no Result section.")
    try:
        decoded_value = json.loads(result_match.group("result").strip())
    except json.JSONDecodeError as error:
        raise BrowserAgentError("Playwright browser_evaluate response is not JSON text.") from error
    if not isinstance(decoded_value, str):
        raise BrowserAgentError("Playwright browser_evaluate response is not a text value.")
    return decoded_value


def _error_message(result: CallToolResult) -> str:
    """Return a useful remote error from an error result."""

    text_content = [
        content_item.text
        for content_item in result.content
        if isinstance(content_item, TextContent)
    ]
    if text_content:
        return "\n".join(text_content)
    return "Playwright MCP reported a tool error."
