"""Tests for best-effort model-reasoning progress reporting."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import pytest

from render_and_strip_mcp.reasoning_progress import (
    ProgressReporter,
)


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


@dataclass
class FakeRenewableTimeout:
    """Record timeout renewals without depending on elapsed wall-clock time."""

    renewal_count: int = 0

    def renew(self) -> None:
        self.renewal_count += 1


def test_zero_interval_delivers_non_blank_fragments_immediately() -> None:
    """Each non-blank fragment is delivered immediately when the interval is zero."""

    context = FakeProgressContext()
    reporter = ProgressReporter(0, 0, context)  # type: ignore[arg-type]

    async def exercise() -> None:
        await reporter.accept("  ")
        await reporter.accept(" first ")
        await reporter.accept("second")

    asyncio.run(exercise())

    assert context.notifications == [(1, "first"), (1, "second")]


def test_progress_reports_are_logged_at_debug_level(caplog: pytest.LogCaptureFixture) -> None:
    """Each accepted non-blank progress fragment is available for debug troubleshooting."""

    caplog.set_level(logging.DEBUG, logger="render_and_strip_mcp.reasoning_progress")
    context = FakeProgressContext()
    reporter = ProgressReporter(0, 0, context)  # type: ignore[arg-type]

    asyncio.run(reporter.accept("model reasoning"))

    assert context.notifications == [(1, "model reasoning")]
    assert caplog.messages == ["Accepting fragment: model reasoning"]


def test_reporter_renews_supplied_timeout_for_meaningful_progress() -> None:
    """Meaningful reasoning renews its supplied model timeout before delivery."""

    context = FakeProgressContext()
    reporter = ProgressReporter(0, 0, context)  # type: ignore[arg-type]
    model_timeout = FakeRenewableTimeout()

    async def exercise() -> None:
        await reporter.accept(
            "model reasoning",
            timeout_to_renew=model_timeout,  # type: ignore[arg-type]
        )
        await reporter.accept_operational_status("Access")

    asyncio.run(exercise())

    assert model_timeout.renewal_count == 1
    assert context.notifications == [(1, "model reasoning"), (1, "[status] Access")]


def test_reporter_does_not_renew_supplied_timeout_for_blank_progress() -> None:
    """Empty stream fragments do not keep a model request alive."""

    context = FakeProgressContext()
    reporter = ProgressReporter(0, 0, context)  # type: ignore[arg-type]
    model_timeout = FakeRenewableTimeout()

    async def exercise() -> None:
        await reporter.accept(
            "  ",
            timeout_to_renew=model_timeout,  # type: ignore[arg-type]
        )

    asyncio.run(exercise())

    assert model_timeout.renewal_count == 0
    assert context.notifications == []


def test_positive_batch_limit_retains_later_fragments_in_order() -> None:
    """A positive maximum bounds each delivery without capping the invocation."""

    clock = FakeClock()
    context = FakeProgressContext()
    reporter = ProgressReporter(2, 5, context, clock)  # type: ignore[arg-type]

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
        (2, "first\nsecond"),
        (2, "[status] Access\nfourth"),
    ]


def test_unlimited_batch_delivers_all_buffered_fragments_when_eligible() -> None:
    """A zero maximum leaves the next eligible batch unbounded."""

    clock = FakeClock()
    context = FakeProgressContext()
    reporter = ProgressReporter(0, 5, context, clock)  # type: ignore[arg-type]

    async def exercise() -> None:
        await reporter.accept("first")
        clock.current_time = 1
        await reporter.accept("second")
        await reporter.accept("third")
        clock.current_time = 5
        await reporter.flush_if_needed()

    asyncio.run(exercise())

    assert context.notifications == [(3, "first\nsecond\nthird")]


def test_positive_interval_delays_the_initial_progress_delivery() -> None:
    """The first batch remains buffered until the positive configured interval elapses."""

    clock = FakeClock()
    context = FakeProgressContext()
    reporter = ProgressReporter(0, 5, context, clock)  # type: ignore[arg-type]

    async def exercise() -> None:
        await reporter.accept("first")
        clock.current_time = 1
        await reporter.accept("second")
        clock.current_time = 4
        await reporter.flush_if_needed()
        clock.current_time = 5
        await reporter.flush_if_needed()

    asyncio.run(exercise())

    assert context.notifications == [(2, "first\nsecond")]


def test_delivery_failure_is_non_fatal_and_later_batches_remain_eligible(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A reporting error does not prevent a later progress delivery attempt."""

    context = FakeProgressContext(delivery_error=RuntimeError("notification unavailable"))
    reporter = ProgressReporter(0, 0, context)  # type: ignore[arg-type]

    async def exercise() -> None:
        await reporter.accept("first")
        context.delivery_error = None
        await reporter.accept("second")
        await reporter.flush_if_needed()

    asyncio.run(exercise())

    assert context.notifications == [(1, "first"), (1, "second")]
    assert "Reasoning progress delivery failed" in caplog.text
