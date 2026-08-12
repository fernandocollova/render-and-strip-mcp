"""Tests for renewable asynchronous deadlines."""

from __future__ import annotations

import asyncio

import pytest

from render_and_strip_mcp.renewable_timeout import RenewableTimeout


def test_renew_resets_deadline_to_original_duration_from_now() -> None:
    """Renewal replaces rather than extends the active absolute deadline."""

    async def exercise() -> tuple[float, float, float]:
        timeout = RenewableTimeout(30)
        async with timeout:
            initial_deadline = timeout.when()
            assert initial_deadline is not None
            event_loop = asyncio.get_running_loop()
            renewal_time = event_loop.time()
            timeout.renew()
            renewed_deadline = timeout.when()
            assert renewed_deadline is not None
            return initial_deadline, renewal_time, renewed_deadline

    initial_deadline, renewal_time, renewed_deadline = asyncio.run(exercise())

    assert renewed_deadline == pytest.approx(renewal_time + 30, abs=0.01)
    assert renewed_deadline >= initial_deadline


def test_timeout_preserves_asyncio_timeout_error_behavior() -> None:
    """The wrapper converts cancellation caused by its deadline into TimeoutError."""

    async def exercise() -> None:
        async with RenewableTimeout(0):
            await asyncio.sleep(0)

    with pytest.raises(TimeoutError):
        asyncio.run(exercise())


def test_timeout_cannot_be_renewed_before_entry() -> None:
    """Invalid lifecycle use retains asyncio.Timeout's clear failure."""

    async def exercise() -> None:
        timeout = RenewableTimeout(30)
        with pytest.raises(RuntimeError, match="has not been entered"):
            timeout.renew()

    asyncio.run(exercise())
