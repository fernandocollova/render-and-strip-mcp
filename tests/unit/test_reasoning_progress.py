"""Tests for best-effort model-reasoning progress reporting."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from render_and_strip_mcp.reasoning_progress import ReasoningProgressReporter


@dataclass
class FakeClock:
    """Controllable monotonic clock for interval-coalescing tests."""

    current_time: float = 0

    def __call__(self) -> float:
        return self.current_time


@dataclass
class FakeProgressContext:
    """Capture progress reports sent through the FastMCP context boundary."""

    notifications: list[tuple[float, str | None]] = field(default_factory=list)
    delivery_error: Exception | None = None

    async def report_progress(self, *, progress: float, message: str | None = None) -> None:
        self.notifications.append((progress, message))
        if self.delivery_error is not None:
            raise self.delivery_error


def test_zero_interval_delivers_non_blank_fragments_immediately() -> None:
    """Each non-blank fragment is delivered immediately when the interval is zero."""

    context = FakeProgressContext()
    reporter = ReasoningProgressReporter(0, 0, context)  # type: ignore[arg-type]

    async def exercise() -> None:
        await reporter.accept("  ")
        await reporter.accept(" first ")
        await reporter.accept("second")

    asyncio.run(exercise())

    assert context.notifications == [(1, "first"), (1, "second")]


def test_positive_batch_limit_retains_later_fragments_in_order() -> None:
    """A positive maximum bounds each delivery without capping the invocation."""

    clock = FakeClock()
    context = FakeProgressContext()
    reporter = ReasoningProgressReporter(2, 5, context, clock)  # type: ignore[arg-type]

    async def exercise() -> None:
        await reporter.accept("first")
        clock.current_time = 1
        await reporter.accept("second")
        await reporter.accept_operational_status("Access")
        await reporter.accept("fourth")
        clock.current_time = 5
        await reporter.flush_if_needed()
        clock.current_time = 10
        await reporter.flush_if_needed()

    asyncio.run(exercise())

    assert context.notifications == [
        (1, "first"),
        (2, "second\n[status] Access"),
        (1, "fourth"),
    ]


def test_unlimited_batch_delivers_all_buffered_fragments_when_eligible() -> None:
    """A zero maximum leaves the next eligible batch unbounded."""

    clock = FakeClock()
    context = FakeProgressContext()
    reporter = ReasoningProgressReporter(0, 5, context, clock)  # type: ignore[arg-type]

    async def exercise() -> None:
        await reporter.accept("first")
        clock.current_time = 1
        await reporter.accept("second")
        await reporter.accept("third")
        clock.current_time = 5
        await reporter.flush_if_needed()

    asyncio.run(exercise())

    assert context.notifications == [(1, "first"), (2, "second\nthird")]


def test_flush_if_needed_does_not_bypass_a_positive_interval() -> None:
    """Cleanup checks leave pending fragments buffered until the interval elapses."""

    clock = FakeClock()
    context = FakeProgressContext()
    reporter = ReasoningProgressReporter(0, 5, context, clock)  # type: ignore[arg-type]

    async def exercise() -> None:
        await reporter.accept("first")
        clock.current_time = 1
        await reporter.accept("second")
        clock.current_time = 4
        await reporter.flush_if_needed()
        clock.current_time = 5
        await reporter.flush_if_needed()

    asyncio.run(exercise())

    assert context.notifications == [(1, "first"), (1, "second")]


def test_delivery_failure_is_non_fatal_and_later_batches_remain_eligible(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A reporting error does not prevent a later progress delivery attempt."""

    context = FakeProgressContext(delivery_error=RuntimeError("notification unavailable"))
    reporter = ReasoningProgressReporter(0, 0, context)  # type: ignore[arg-type]

    async def exercise() -> None:
        await reporter.accept("first")
        context.delivery_error = None
        await reporter.accept("second")
        await reporter.flush_if_needed()

    asyncio.run(exercise())

    assert context.notifications == [(1, "first"), (1, "second")]
    assert "Reasoning progress delivery failed" in caplog.text
