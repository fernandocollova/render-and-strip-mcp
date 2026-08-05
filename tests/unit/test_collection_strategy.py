"""Tests for the retained-final-document collection strategy dispatch."""

from __future__ import annotations

import asyncio

import pytest

import render_and_strip_mcp.collection_strategy as collection_strategy
from render_and_strip_mcp.agent_context import PageState
from render_and_strip_mcp.agent_loop import StageRunResult
from render_and_strip_mcp.config import AgentSettings, LlmSettings
from render_and_strip_mcp.errors import UnsuccessfulStageOutcomeError
from render_and_strip_mcp.playwright_tools import ToolCatalog
from render_and_strip_mcp.stage_models import CollectionReport


def llm_settings() -> LlmSettings:
    """Build model settings for collection-only unit tests."""

    return LlmSettings(
        model="test-model",
        api_base="https://model.example/v1",
        api_key="test-key",
    )


def test_retained_strategy_returns_only_a_complete_final_page_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incomplete collection evidence fails before the caller can extract any document."""

    initial_state = PageState("fresh snapshot", "https://example.test/report")

    async def incomplete_stage(*arguments: object, **keyword_arguments: object) -> StageRunResult:
        return StageRunResult(
            CollectionReport(complete=False, evidence=["More content may remain."]), initial_state
        )

    monkeypatch.setattr(collection_strategy, "run_stage", incomplete_stage)

    async def unused_action(*arguments: object) -> PageState:
        raise AssertionError("collection should not execute remote actions in this fake")

    with pytest.raises(UnsuccessfulStageOutcomeError, match="did not complete"):
        asyncio.run(
            collection_strategy.collect_retained_final_document(
                llm_settings(),
                AgentSettings(),
                ToolCatalog([], {}),
                "collect the report",
                initial_state,
                unused_action,
            )
        )


def test_strategy_dispatch_has_no_unknown_handler() -> None:
    """Unsupported discovery does not silently select a fallback collection implementation."""

    assert set(collection_strategy.COLLECTION_STRATEGIES) == {"retained-final-document"}
