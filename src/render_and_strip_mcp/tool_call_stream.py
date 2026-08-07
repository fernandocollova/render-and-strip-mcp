"""Reassemble and validate one fragmented LiteLLM function-tool call.

OpenAI-compatible streaming endpoints emit tool calls as deltas: an ID and function name may
arrive in one chunk while the JSON argument text arrives across later chunks. LiteLLM provides a
common streaming request interface and normalizes provider response shapes, but it yields those
individual chunks; it does not produce this application's final, policy-validated tool call.

The OpenAI SDK has its own stream accumulator, but it expects OpenAI SDK chunk models and OpenAI
stream semantics. This module deliberately accepts LiteLLM's mapping- and attribute-shaped chunks
so the browser agent retains its provider abstraction. It adds the application-specific rules that
the SDK cannot know: a turn permits exactly one call, the call must name a catalogued tool, and it
must have a complete JSON-object argument payload before it can be executed.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from .errors import ModelStreamError
from .playwright_tools import ToolCatalog


@dataclass(frozen=True)
class RequestedToolCall:
    """One complete model-requested remote action or local stage completion."""

    model_tool_name: str
    call_id: str
    arguments: dict[str, Any]
    kind: Literal["remote", "completion"] = "remote"


@dataclass
class ToolCallAccumulator:
    """Mutable state for one fragmented streamed function call in a model turn."""

    call_id: str | None = None
    model_tool_name: str | None = None
    argument_parts: list[str] | None = None
    was_requested: bool = False

    def add_fragment(self, fragment: object) -> None:
        """Validate and retain one OpenAI-compatible streamed tool-call delta."""

        if not isinstance(fragment, Mapping) and not hasattr(fragment, "index"):
            raise ModelStreamError("Model stream contains an invalid tool-call fragment.")
        index = _field(fragment, "index")
        if index != 0:
            raise ModelStreamError("Model requested multiple tool calls in one turn.")
        self.was_requested = True
        call_id = _field(fragment, "id")
        if call_id is not None:
            self.call_id = _merge_fragment_value("tool-call ID", self.call_id, call_id)
        function = _field(fragment, "function")
        if function is None:
            return
        function_name = _field(function, "name")
        if function_name is not None:
            self.model_tool_name = _merge_fragment_value(
                "tool name", self.model_tool_name, function_name
            )
        arguments = _field(function, "arguments")
        if arguments is not None:
            if not isinstance(arguments, str):
                raise ModelStreamError("Model stream tool-call arguments must be text.")
            if self.argument_parts is None:
                self.argument_parts = []
            self.argument_parts.append(arguments)

    def complete(self, tool_catalog: ToolCatalog, terminal_reason: str) -> RequestedToolCall | None:
        """Return the completed catalogued call, or ``None`` for an ordinary stop."""

        if not self.was_requested:
            if terminal_reason != "stop":
                raise ModelStreamError("Model ended with tool_calls but supplied no tool call.")
            return None
        if terminal_reason != "tool_calls":
            raise ModelStreamError(
                "Model supplied a tool call without a tool_calls completion reason."
            )
        if not self.call_id or not self.model_tool_name or self.argument_parts is None:
            raise ModelStreamError("Model stream contains an incomplete tool call.")
        if self.model_tool_name in tool_catalog.remote_name_by_model_name:
            tool_kind: Literal["remote", "completion"] = "remote"
        elif (
            tool_catalog.completion_tool is not None
            and self.model_tool_name == tool_catalog.completion_tool.name
        ):
            tool_kind = "completion"
        else:
            raise ModelStreamError(f"Model requested unknown tool {self.model_tool_name!r}.")
        try:
            decoded_arguments = json.loads("".join(self.argument_parts))
        except json.JSONDecodeError as error:
            raise ModelStreamError("Model supplied invalid tool-call JSON arguments.") from error
        if not isinstance(decoded_arguments, dict):
            raise ModelStreamError("Model tool-call arguments must decode to an object.")
        return RequestedToolCall(
            model_tool_name=self.model_tool_name,
            call_id=self.call_id,
            arguments=decoded_arguments,
            kind=tool_kind,
        )


def accumulate_tool_call_fragments(delta: object, accumulator: ToolCallAccumulator) -> None:
    """Collect at most one fragmented function call from a LiteLLM stream delta."""

    tool_call_fragments = _field(delta, "tool_calls")
    if tool_call_fragments is None:
        return
    if not isinstance(tool_call_fragments, list) or len(tool_call_fragments) > 1:
        raise ModelStreamError("Model requested multiple or malformed tool calls in one turn.")
    if tool_call_fragments:
        accumulator.add_fragment(tool_call_fragments[0])


def _field(value: object, name: str) -> object:
    """Read a field from LiteLLM's mapping or attribute-based response objects."""

    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _merge_fragment_value(field_name: str, existing_value: str | None, value: object) -> str:
    """Accept an initial fragment value or an identical repeated value."""

    if not isinstance(value, str) or not value:
        raise ModelStreamError(f"Model stream {field_name} must be non-empty text.")
    if existing_value is not None and existing_value != value:
        raise ModelStreamError(f"Model stream changed its {field_name} mid-call.")
    return value
