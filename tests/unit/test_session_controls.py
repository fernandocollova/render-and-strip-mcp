"""Tests for dependency translation and cancellation cleanup."""

from __future__ import annotations

import asyncio

import httpx
import litellm
import pytest
from fastmcp.exceptions import ToolError
from openai import APIConnectionError

import render_and_strip_mcp.browser_agent as browser_agent_module
from render_and_strip_mcp.agent_context import Stage
from render_and_strip_mcp.agent_loop import StageRunner, StageRunResult

from .test_browser_agent import (
    FakeBrowserClient,
    RecordingProgressReporter,
    install_fake_session,
    settings,
)


@pytest.mark.parametrize(
    ("dependency_error", "expected_error", "expected_message"),
    [
        (
            litellm.ContextWindowExceededError("too large", "test-model", "openai"),
            litellm.ContextWindowExceededError,
            "too large",
        ),
        (
            APIConnectionError(
                message="provider offline",
                request=httpx.Request("POST", "https://model.example/v1/chat/completions"),
            ),
            APIConnectionError,
            "provider offline",
        ),
        (ToolError("remote browser failed"), ToolError, "remote browser failed"),
    ],
)
def test_dependency_errors_propagate_and_clean_up(
    monkeypatch: pytest.MonkeyPatch,
    dependency_error: Exception,
    expected_error: type[Exception],
    expected_message: str,
) -> None:
    """Dependency errors propagate from the agent after browser cleanup."""

    client = FakeBrowserClient(["https://example.test/start"] * 2)
    install_fake_session(monkeypatch, client)

    async def fail_stage(
        self: StageRunner,
        stage: Stage,
        task: str,
        initial_state: object,
    ) -> StageRunResult:
        del self, stage, task, initial_state
        raise dependency_error

    monkeypatch.setattr(browser_agent_module.StageRunner, "run", fail_stage)

    with pytest.raises(expected_error, match=expected_message):
        asyncio.run(
            browser_agent_module.BrowserAgent(
                settings(),
                RecordingProgressReporter(),  # type: ignore[arg-type]
            ).run("https://example.test/", "task")
        )

    assert client.calls[-1] == ("browser_close", {})


def test_cancellation_shields_browser_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cancellation still invokes browser_close exactly once before propagating."""

    client = FakeBrowserClient(["https://example.test/start"] * 2)
    install_fake_session(monkeypatch, client)
    entered_stage = asyncio.Event()
    unblock_stage = asyncio.Event()

    async def blocked_stage(
        self: StageRunner,
        stage: Stage,
        task: str,
        initial_state: object,
    ) -> StageRunResult:
        del self, stage, task, initial_state
        entered_stage.set()
        await unblock_stage.wait()
        raise AssertionError("The stage should have been cancelled.")

    monkeypatch.setattr(browser_agent_module.StageRunner, "run", blocked_stage)

    async def exercise() -> None:
        invocation = asyncio.create_task(
            browser_agent_module.BrowserAgent(
                settings(),
                RecordingProgressReporter(),  # type: ignore[arg-type]
            ).run("https://example.test/", "task")
        )
        await entered_stage.wait()
        invocation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await invocation

    asyncio.run(exercise())

    assert [tool_name for tool_name, _ in client.calls].count("browser_close") == 1
