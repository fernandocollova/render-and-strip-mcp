"""Tests for dependency translation, cancellation cleanup, and concurrency gates."""

from __future__ import annotations

import asyncio

import httpx
import litellm
import pytest
from fastmcp.exceptions import ToolError
from openai import APIConnectionError

import render_and_strip_mcp.browser_agent as browser_agent_module
from render_and_strip_mcp.agent_context import BrowserActionResult
from render_and_strip_mcp.errors import BrowserAgentError
from render_and_strip_mcp.invocation_gate import InvocationGate

from .test_browser_agent import FakeBrowserClient, install_fake_session, settings


@pytest.mark.parametrize(
    ("dependency_error", "expected_message"),
    [
        (
            litellm.ContextWindowExceededError("too large", "test-model", "openai"),
            "Model context exhausted:",
        ),
        (
            APIConnectionError(
                message="provider offline",
                request=httpx.Request("POST", "https://model.example/v1/chat/completions"),
            ),
            "provider offline",
        ),
        (ToolError("remote browser failed"), "remote browser failed"),
    ],
)
def test_dependency_errors_are_translated_and_cleaned_up(
    monkeypatch: pytest.MonkeyPatch,
    dependency_error: Exception,
    expected_message: str,
) -> None:
    """Only documented provider and remote dependency errors receive outward translation."""

    client = FakeBrowserClient(["https://example.test/start"])
    install_fake_session(monkeypatch, client)

    async def fail_run_loop(*arguments: object) -> BrowserActionResult:
        raise dependency_error

    monkeypatch.setattr(browser_agent_module, "run_agent_loop", fail_run_loop)

    with pytest.raises(BrowserAgentError, match=expected_message):
        asyncio.run(
            browser_agent_module.BrowserAgent(settings(), InvocationGate(0)).run(
                "https://example.test/", "task"
            )
        )

    assert client.calls[-1] == ("browser_close", {})


def test_cancellation_shields_browser_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cancellation still invokes browser_close exactly once before propagating."""

    client = FakeBrowserClient(["https://example.test/start"])
    install_fake_session(monkeypatch, client)
    entered_agent_loop = asyncio.Event()
    unblock_agent_loop = asyncio.Event()

    async def blocked_run_loop(*arguments: object) -> BrowserActionResult:
        entered_agent_loop.set()
        await unblock_agent_loop.wait()
        raise AssertionError("The agent loop should have been cancelled.")

    monkeypatch.setattr(browser_agent_module, "run_agent_loop", blocked_run_loop)

    async def exercise() -> None:
        invocation = asyncio.create_task(
            browser_agent_module.BrowserAgent(settings(), InvocationGate(0)).run(
                "https://example.test/", "task"
            )
        )
        await entered_agent_loop.wait()
        invocation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await invocation

    asyncio.run(exercise())

    assert [tool_name for tool_name, _ in client.calls].count("browser_close") == 1


def test_positive_concurrency_gate_waits_without_timing_assertions() -> None:
    """A second positive-limit acquisition cannot enter until the first releases its slot."""

    gate = InvocationGate(1)

    async def exercise() -> None:
        first_entered = asyncio.Event()
        allow_first_to_finish = asyncio.Event()
        second_entered = asyncio.Event()

        async def first_invocation() -> None:
            async with gate.acquire():
                first_entered.set()
                await allow_first_to_finish.wait()

        async def second_invocation() -> None:
            async with gate.acquire():
                second_entered.set()

        first_task = asyncio.create_task(first_invocation())
        await first_entered.wait()
        second_task = asyncio.create_task(second_invocation())
        await asyncio.sleep(0)
        assert second_entered.is_set() is False
        allow_first_to_finish.set()
        await asyncio.gather(first_task, second_task)
        assert second_entered.is_set() is True

    asyncio.run(exercise())
