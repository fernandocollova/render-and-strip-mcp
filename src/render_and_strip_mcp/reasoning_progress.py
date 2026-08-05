"""Best-effort forwarding of streamed model reasoning as MCP progress."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

ProgressDelivery = Callable[[float, float | None, str | None], Awaitable[None]]
Clock = Callable[[], float]


class ReasoningProgressReporter:
    """Apply invocation-wide item limits and interval coalescing to reasoning deltas."""

    def __init__(
        self,
        maximum_items: int,
        minimum_interval_seconds: float,
        deliver_progress: ProgressDelivery | None,
        clock: Clock = time.monotonic,
    ):
        self._maximum_items = maximum_items
        self._minimum_interval_seconds = minimum_interval_seconds
        self._deliver_progress = deliver_progress
        self._clock = clock
        self._accepted_item_count = 0
        self._last_delivery_time: float | None = None
        self._buffered_fragments: list[str] = []
        self._delivery_enabled = deliver_progress is not None
        if deliver_progress is None:
            logger.warning("Reasoning progress delivery is unavailable for this invocation.")

    @property
    def accepted_item_count(self) -> int:
        """Return the invocation-wide count of accepted non-empty reasoning deltas."""

        return self._accepted_item_count

    async def accept(self, reasoning_fragment: str) -> None:
        """Accept one normalized fragment and emit or coalesce it under configured policy."""

        normalized_fragment = reasoning_fragment.strip()
        if not normalized_fragment:
            return
        if self._maximum_items and self._accepted_item_count >= self._maximum_items:
            return
        self._accepted_item_count += 1
        self._buffered_fragments.append(normalized_fragment)
        if self._minimum_interval_seconds == 0:
            await self.flush()
            return
        current_time = self._clock()
        if (
            self._last_delivery_time is None
            or current_time - self._last_delivery_time >= self._minimum_interval_seconds
        ):
            await self.flush()

    async def flush(self) -> None:
        """Immediately send any buffered reasoning text without changing the item count."""

        if not self._buffered_fragments:
            return
        message = "\n".join(self._buffered_fragments)
        self._buffered_fragments.clear()
        if not self._delivery_enabled or self._deliver_progress is None:
            return
        try:
            await self._deliver_progress(
                self._accepted_item_count,
                self._maximum_items or None,
                message,
            )
        except Exception as error:
            self._delivery_enabled = False
            logger.warning("Reasoning progress delivery failed: %s", error)
            return
        self._last_delivery_time = self._clock()
