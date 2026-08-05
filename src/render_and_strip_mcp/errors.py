"""Domain errors raised while processing a browser-rendering request."""

from __future__ import annotations


class BrowserAgentError(Exception):
    """A browser-agent request cannot produce a complete result."""


class BrowserCompatibilityError(BrowserAgentError):
    """The configured Playwright MCP server lacks a required capability."""


class ToolSchemaError(BrowserAgentError):
    """A remote MCP tool cannot be represented as an OpenAI function tool."""


class ModelStreamError(BrowserAgentError):
    """The configured model emitted an unsupported streamed completion."""


class ExecutionLimitError(BrowserAgentError):
    """A configured browser-agent execution limit was exceeded."""
