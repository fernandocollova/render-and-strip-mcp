"""Best-effort forwarding of streamed model reasoning as MCP progress."""

from __future__ import annotations

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
        try:
            await self._context.report_progress(
                progress=len(batch_fragments),
                message="\n".join(batch_fragments),
            )
        except Exception as error:
            logger.warning("Reasoning progress delivery failed: %s", error)
            return
        self._last_delivery_time = self._clock()
