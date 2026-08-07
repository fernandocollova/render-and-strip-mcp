"""LiteLLM streaming support for one browser-agent model turn."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

import litellm

from .config import LlmSettings
from .errors import ModelStreamError
from .playwright_tools import ToolCatalog
from .tool_call_stream import (
    RequestedToolCall,
    ToolCallAccumulator,
    accumulate_tool_call_fragments,
)

ReasoningHandler = Callable[[str], Awaitable[None]]


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
    on_reasoning_fragment: ReasoningHandler,
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
    tool_call_state = ToolCallAccumulator()
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
        accumulate_tool_call_fragments(delta, tool_call_state)
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
    on_reasoning_fragment: ReasoningHandler,
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
        await on_reasoning_fragment(reasoning_content)


def _field(value: object, name: str) -> object:
    """Read a field from LiteLLM's mapping or attribute-based response objects."""

    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)
