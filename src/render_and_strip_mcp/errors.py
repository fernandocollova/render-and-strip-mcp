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


class StageCompletionError(BrowserAgentError):
    """A model-guided stage did not provide a valid required completion report."""


class MissingStageCompletionError(StageCompletionError):
    """A model stage stopped without calling its required local completion tool."""


class MalformedStageCompletionError(StageCompletionError):
    """A local completion-tool payload failed its strict stage schema."""


class UnknownDiscoveryStrategyError(StageCompletionError):
    """Discovery could not establish a supported retained-document strategy."""


class UnsupportedCollectionStrategyError(StageCompletionError):
    """The selected collection strategy has no implementation."""


class UnsuccessfulStageOutcomeError(StageCompletionError):
    """A stage reported an explicitly unsuccessful terminal result."""


class StageToolCollisionError(StageCompletionError):
    """A remote Playwright tool conflicts with a local stage completion tool."""
