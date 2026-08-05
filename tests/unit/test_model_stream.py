"""Tests for constrained LiteLLM streaming behavior."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

import render_and_strip_mcp.model_stream as model_stream
from render_and_strip_mcp.config import LlmSettings
from render_and_strip_mcp.errors import ModelStreamError
from render_and_strip_mcp.playwright_tools import ToolCatalog
from render_and_strip_mcp.stage_models import ACCESS_COMPLETION_TOOL


def llm_settings() -> LlmSettings:
    """Build a test-only model endpoint configuration."""

    return LlmSettings(
        model="test-model",
        api_base="https://model.example/v1",
        api_key="test-key",
    )


def catalog() -> ToolCatalog:
    """Build the small callable-tool catalog used by stream tests."""

    return ToolCatalog(
        openai_tools=[{"type": "function", "function": {"name": "browser_click"}}],
        remote_name_by_model_name={"browser_click": "browser_click"},
    )


async def chunks(items: list[dict[str, object]]) -> AsyncIterator[dict[str, object]]:
    """Yield static chunks through the async-stream protocol."""

    for item in items:
        yield item


def test_stream_accumulates_fragmented_tool_call_and_fixed_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid fragmented tool call is accumulated with deterministic LiteLLM parameters."""

    observed: dict[str, object] = {}

    async def fake_acompletion(**kwargs: object) -> AsyncIterator[dict[str, object]]:
        observed.update(kwargs)
        return chunks(
            [
                {
                    "choices": [
                        {
                            "delta": {
                                "reasoning_content": "think ",
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call-1",
                                        "function": {"name": "browser_click", "arguments": "{"},
                                    }
                                ],
                            },
                            "finish_reason": None,
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "reasoning_content": "now",
                                "tool_calls": [{"index": 0, "function": {"arguments": "}"}}],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                },
            ]
        )

    monkeypatch.setattr(model_stream.litellm, "acompletion", fake_acompletion)

    result = asyncio.run(
        model_stream.stream_model_turn(
            llm_settings(),
            catalog(),
            [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
        )
    )

    assert result.tool_call is not None
    assert result.tool_call.arguments == {}
    assert result.reasoning_fragments == ("think ", "now")
    assert {
        key: observed[key]
        for key in {
            "stream",
            "tool_choice",
            "temperature",
            "parallel_tool_calls",
            "num_retries",
            "max_tokens",
        }
    } == {
        "stream": True,
        "tool_choice": "auto",
        "temperature": 0,
        "parallel_tool_calls": False,
        "num_retries": 0,
        "max_tokens": 1024,
    }
    assert "reasoning_effort" not in observed
    assert "seed" not in observed
    assert "response_format" not in observed


def test_stream_routes_local_completion_call_separately_from_remote_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stream parser preserves the execution route selected by a validated tool name."""

    async def fake_acompletion(**kwargs: object) -> AsyncIterator[dict[str, object]]:
        return chunks(
            [
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call-1",
                                        "function": {
                                            "name": "complete_access",
                                            "arguments": (
                                                '{"target_state":"ready",'
                                                '"reconstruction_instructions":[],'
                                                '"verification":["visible"]}'
                                            ),
                                        },
                                    }
                                ]
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                }
            ]
        )

    monkeypatch.setattr(model_stream.litellm, "acompletion", fake_acompletion)

    result = asyncio.run(
        model_stream.stream_model_turn(
            llm_settings(),
            ToolCatalog([], {"browser_click": "browser_click"}).with_completion_tool(
                ACCESS_COMPLETION_TOOL
            ),
            [],
        )
    )

    assert result.tool_call is not None
    assert result.tool_call.kind == "completion"
    assert result.tool_call.model_tool_name == "complete_access"


@pytest.mark.parametrize(
    ("stream_chunks", "error_message"),
    [
        ([{"choices": [{"delta": {}, "finish_reason": "length"}]}], "unsupported reason"),
        (
            [{"choices": [{"delta": {"tool_calls": [{"index": 1}]}, "finish_reason": None}]}],
            "multiple",
        ),
        ([{"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}], "no tool call"),
    ],
)
def test_stream_rejects_malformed_or_non_normal_completion(
    monkeypatch: pytest.MonkeyPatch,
    stream_chunks: list[dict[str, object]],
    error_message: str,
) -> None:
    """Malformed, parallel, and non-normal provider streams are hard failures."""

    async def fake_acompletion(**kwargs: object) -> AsyncIterator[dict[str, object]]:
        return chunks(stream_chunks)

    monkeypatch.setattr(model_stream.litellm, "acompletion", fake_acompletion)

    with pytest.raises(ModelStreamError, match=error_message):
        asyncio.run(model_stream.stream_model_turn(llm_settings(), catalog(), []))
