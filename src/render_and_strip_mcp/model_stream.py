"""LiteLLM streaming support for one browser-agent model turn."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

import litellm

from .config import LlmSettings
from .errors import ModelStreamError
from .playwright_tools import ToolCatalog

ReasoningHandler = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class RequestedToolCall:
    """One complete model-requested remote action or local stage completion."""

    model_tool_name: str
    call_id: str
    arguments: dict[str, Any]
    kind: Literal["remote", "completion"] = "remote"


@dataclass(frozen=True)
class ModelTurn:
    """The complete result of a normal streamed model turn."""

    content: str
    tool_call: RequestedToolCall | None
    reasoning_fragments: tuple[str, ...]


async def stream_model_turn(
    llm_settings: LlmSettings,
    tool_catalog: ToolCatalog,
    messages: list[dict[str, str]],
    on_reasoning_fragment: ReasoningHandler | None = None,
) -> ModelTurn:
    """Run one constrained OpenAI-compatible streamed function-tool request."""

    stream = await litellm.acompletion(
        model=llm_settings.model,
        messages=messages,
        tools=tool_catalog.openai_tools,
        stream=True,
        tool_choice="auto",
        temperature=0,
        parallel_tool_calls=False,
        num_retries=0,
        max_tokens=llm_settings.max_output_tokens,
        api_base=str(llm_settings.api_base),
        api_key=llm_settings.api_key.get_secret_value(),
    )
    if not hasattr(stream, "__aiter__"):
        raise ModelStreamError("Model endpoint returned a non-streaming completion.")

    content_parts: list[str] = []
    reasoning_fragments: list[str] = []
    tool_call_state = _ToolCallState()
    terminal_reason: str | None = None

    async for chunk in stream:
        if terminal_reason is not None:
            raise ModelStreamError("Model emitted data after a terminal completion reason.")
        choice = _single_choice(chunk)
        finish_reason = _field(choice, "finish_reason")
        delta = _field(choice, "delta")
        if delta is None:
            raise ModelStreamError("Model stream choice is missing a delta.")
        await _accumulate_text_parts(
            delta,
            content_parts,
            reasoning_fragments,
            on_reasoning_fragment,
        )
        _accumulate_tool_call_fragments(delta, tool_call_state)
        if finish_reason is not None:
            if not isinstance(finish_reason, str):
                raise ModelStreamError("Model stream has a non-string terminal reason.")
            terminal_reason = finish_reason

    if terminal_reason not in {"stop", "tool_calls"}:
        raise ModelStreamError(f"Model stream ended with unsupported reason {terminal_reason!r}.")
    tool_call = tool_call_state.complete(tool_catalog, terminal_reason)
    return ModelTurn(
        content="".join(content_parts),
        tool_call=tool_call,
        reasoning_fragments=tuple(reasoning_fragments),
    )


@dataclass
class _ToolCallState:
    """Mutable accumulation state for a single fragmented streamed function call."""

    call_id: str | None = None
    model_tool_name: str | None = None
    argument_parts: list[str] | None = None
    was_requested: bool = False

    def add_fragment(self, fragment: object) -> None:
        """Validate and accumulate one OpenAI streamed tool-call fragment."""

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
        """Turn valid accumulated state into one complete request or a normal stop."""

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


def _single_choice(chunk: object) -> object:
    """Return the one supported chat-completion choice from a streamed chunk."""

    choices = _field(chunk, "choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ModelStreamError("Model stream chunk must contain exactly one choice.")
    return choices[0]


async def _accumulate_text_parts(
    delta: object,
    content_parts: list[str],
    reasoning_fragments: list[str],
    on_reasoning_fragment: ReasoningHandler | None,
) -> None:
    """Collect ordinary content and optional reasoning independently of tool calls."""

    content = _field(delta, "content")
    if content is not None:
        if not isinstance(content, str):
            raise ModelStreamError("Model stream content must be text.")
        content_parts.append(content)
    reasoning_content = _field(delta, "reasoning_content")
    if reasoning_content is not None:
        if not isinstance(reasoning_content, str):
            raise ModelStreamError("Model stream reasoning_content must be text.")
        reasoning_fragments.append(reasoning_content)
        if on_reasoning_fragment is not None:
            await on_reasoning_fragment(reasoning_content)


def _accumulate_tool_call_fragments(delta: object, tool_call_state: _ToolCallState) -> None:
    """Collect at most one fragmented OpenAI function-tool call."""

    tool_call_fragments = _field(delta, "tool_calls")
    if tool_call_fragments is None:
        return
    if not isinstance(tool_call_fragments, list) or len(tool_call_fragments) > 1:
        raise ModelStreamError("Model requested multiple or malformed tool calls in one turn.")
    if tool_call_fragments:
        tool_call_state.add_fragment(tool_call_fragments[0])


def _field(value: object, name: str) -> object:
    """Read a field from LiteLLM's mapping or attribute-based response objects."""

    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _merge_fragment_value(field_name: str, existing_value: str | None, value: object) -> str:
    """Accept the initial value or an identical repeat from a streamed tool call."""

    if not isinstance(value, str) or not value:
        raise ModelStreamError(f"Model stream {field_name} must be non-empty text.")
    if existing_value is not None and existing_value != value:
        raise ModelStreamError(f"Model stream changed its {field_name} mid-call.")
    return value
