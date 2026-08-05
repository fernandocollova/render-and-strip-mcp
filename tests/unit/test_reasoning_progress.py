"""Tests for optional model-reasoning progress reporting."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from render_and_strip_mcp.reasoning_progress import ReasoningProgressReporter


@dataclass
class FakeClock:
    """Controllable monotonic clock for interval-coalescing tests."""

    current_time: float = 0

    def __call__(self) -> float:
        return self.current_time


def test_unlimited_immediate_reasoning_progress_skips_empty_fragments() -> None:
    """Zero interval emits every accepted non-empty normalized reasoning item immediately."""

    notifications: list[tuple[float, float | None, str | None]] = []

    async def deliver(progress: float, total: float | None, message: str | None) -> None:
        notifications.append((progress, total, message))

    reporter = ReasoningProgressReporter(0, 0, deliver)

    async def exercise() -> None:
        await reporter.accept("  ")
        await reporter.accept(" first ")
        await reporter.accept("second")

    asyncio.run(exercise())

    assert reporter.accepted_item_count == 2
    assert notifications == [(1, None, "first"), (2, None, "second")]


def test_reasoning_limit_applies_across_turns() -> None:
    """A positive item maximum persists across independent model-turn callbacks."""

    notifications: list[tuple[float, float | None, str | None]] = []

    async def deliver(progress: float, total: float | None, message: str | None) -> None:
        notifications.append((progress, total, message))

    reporter = ReasoningProgressReporter(2, 0, deliver)

    async def exercise() -> None:
        await reporter.accept("first turn")
        await reporter.accept("second turn")
        await reporter.accept("discarded third turn")

    asyncio.run(exercise())

    assert reporter.accepted_item_count == 2
    assert notifications == [(1, 2, "first turn"), (2, 2, "second turn")]


def test_operational_status_and_reasoning_share_one_ordered_item_limit() -> None:
    """Milestones consume the same invocation-wide budget in their actual acceptance order."""

    notifications: list[tuple[float, float | None, str | None]] = []

    async def deliver(progress: float, total: float | None, message: str | None) -> None:
        notifications.append((progress, total, message))

    reporter = ReasoningProgressReporter(3, 10, deliver)

    async def exercise() -> None:
        await reporter.accept_operational_status("Initial navigation")
        await reporter.accept("model checks the report")
        await reporter.accept_operational_status("Access")
        await reporter.accept("discarded")
        await reporter.flush()

    asyncio.run(exercise())

    assert reporter.accepted_item_count == 3
    assert notifications == [
        (1, 3, "[status] Initial navigation"),
        (3, 3, "model checks the report\n[status] Access"),
    ]


def test_reconstruction_reasoning_is_forwarded_without_orchestration_serializing_checkpoint() -> (
    None
):
    """The shared stream preserves model text that refers to its reconstruction context."""

    notifications: list[str | None] = []

    async def deliver(progress: float, total: float | None, message: str | None) -> None:
        notifications.append(message)

    reporter = ReasoningProgressReporter(0, 0, deliver)

    asyncio.run(reporter.accept("Checkpoint says the report heading must be visible."))

    assert notifications == ["Checkpoint says the report heading must be visible."]


def test_positive_interval_coalesces_then_flushes_pending_text() -> None:
    """Positive intervals coalesce normal notifications while end-of-turn flush bypasses delay."""

    clock = FakeClock()
    notifications: list[tuple[float, float | None, str | None]] = []

    async def deliver(progress: float, total: float | None, message: str | None) -> None:
        notifications.append((progress, total, message))

    reporter = ReasoningProgressReporter(0, 5, deliver, clock)

    async def exercise() -> None:
        await reporter.accept("first")
        clock.current_time = 1
        await reporter.accept("second")
        clock.current_time = 5
        await reporter.accept("third")
        clock.current_time = 6
        await reporter.accept("fourth")
        await reporter.flush()

    asyncio.run(exercise())

    assert notifications == [
        (1, None, "first"),
        (3, None, "second\nthird"),
        (4, None, "fourth"),
    ]


def test_reasoning_item_boundaries_are_provider_dependent() -> None:
    """Each non-empty provider delta is one item regardless of text equivalence."""

    async def deliver(progress: float, total: float | None, message: str | None) -> None:
        return None

    one_fragment_reporter = ReasoningProgressReporter(0, 0, deliver)
    two_fragment_reporter = ReasoningProgressReporter(0, 0, deliver)

    async def exercise() -> None:
        await one_fragment_reporter.accept("combined reasoning")
        await two_fragment_reporter.accept("combined ")
        await two_fragment_reporter.accept("reasoning")

    asyncio.run(exercise())

    assert one_fragment_reporter.accepted_item_count == 1
    assert two_fragment_reporter.accepted_item_count == 2


def test_progress_delivery_failure_disables_future_notifications(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Missing or failing delivery never interrupts model execution or retries reporting."""

    attempts: list[str | None] = []

    async def fail_delivery(progress: float, total: float | None, message: str | None) -> None:
        attempts.append(message)
        raise RuntimeError("notification unavailable")

    reporter = ReasoningProgressReporter(0, 0, fail_delivery)

    async def exercise() -> None:
        await reporter.accept("first")
        await reporter.accept("second")
        await reporter.flush()

    asyncio.run(exercise())

    assert reporter.accepted_item_count == 2
    assert attempts == ["first"]
    assert "Reasoning progress delivery failed" in caplog.text
