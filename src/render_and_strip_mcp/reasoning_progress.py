"""Best-effort forwarding of streamed model reasoning as MCP progress."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

from fastmcp import Context

logger = logging.getLogger(__name__)

Clock = Callable[[], float]


class ReasoningProgressReporter:
    """Batch and rate-limit best-effort reasoning and operational progress deliveries."""

    def __init__(
        self,
        maximum_items: int,
        minimum_interval_seconds: float,
        context: Context,
        clock: Clock = time.monotonic,
    ):
        self._maximum_items = maximum_items
        self._minimum_interval_seconds = minimum_interval_seconds
        self._context = context
        self._clock = clock
        self._last_delivery_time = 0
        self._buffered_fragments: list[str] = []

    async def accept(self, reasoning_fragment: str) -> None:
        """Accept one reasoning fragment or status item under the shared configured policy."""

        normalized_fragment = reasoning_fragment.strip()
        if not normalized_fragment:
            return
        self._buffered_fragments.append(normalized_fragment)
        await self.flush_if_needed()

    async def accept_operational_status(self, status: str) -> None:
        """Submit a clearly labelled orchestration milestone to the shared progress stream."""

        await self.accept(f"[status] {status}")

    async def flush_if_needed(self) -> None:
        """Deliver the next buffered batch only when the configured interval permits it."""

        if not self._buffered_fragments:
            return
        time_since_last_delivery = self._clock() - self._last_delivery_time
        if time_since_last_delivery < self._minimum_interval_seconds:
            return
        if self._maximum_items:
            batch_fragments = self._buffered_fragments[: self._maximum_items]
            del self._buffered_fragments[: self._maximum_items]
        else:
            batch_fragments = self._buffered_fragments
            self._buffered_fragments = []
        message = "\n".join(batch_fragments)
        logger.debug(
            "Reporting reasoning progress with %s item(s): %s",
            len(batch_fragments),
            message,
        )
        try:
            await self._context.report_progress(
                progress=len(batch_fragments),
                message=message,
            )
        except Exception as error:
            logger.warning("Reasoning progress delivery failed: %s", error)
            return
        self._last_delivery_time = self._clock()


class IdleAwareReasoningProgressReporter:
    """Reset an active invocation's idle deadline before forwarding progress."""

    def __init__(
        self,
        reporter: ReasoningProgressReporter,
        idle_timeout: asyncio.Timeout,
        idle_timeout_seconds: float,
    ):
        self._reporter = reporter
        self._idle_timeout = idle_timeout
        self._idle_timeout_seconds = idle_timeout_seconds
        self._event_loop = asyncio.get_running_loop()

    async def accept(self, reasoning_fragment: str) -> None:
        """Record meaningful reasoning activity, then forward it for delivery."""

        if reasoning_fragment.strip():
            self._renew_idle_deadline()
        await self._reporter.accept(reasoning_fragment)

    async def accept_operational_status(self, status: str) -> None:
        """Forward an orchestration milestone as activity and labelled progress."""

        self._renew_idle_deadline()
        await self._reporter.accept_operational_status(status)

    async def flush_if_needed(self) -> None:
        """Forward a pending progress flush under the reporter's delivery policy."""

        await self._reporter.flush_if_needed()

    def _renew_idle_deadline(self) -> None:
        self._idle_timeout.reschedule(self._event_loop.time() + self._idle_timeout_seconds)
