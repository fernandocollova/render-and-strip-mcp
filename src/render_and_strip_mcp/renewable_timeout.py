"""Renewable relative timeout for asynchronous operations."""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Self


class RenewableTimeout:
    """An asyncio timeout that can reset its deadline to its original duration."""

    def __init__(self, timeout_seconds: float):
        self._timeout_seconds = timeout_seconds
        self._timeout = asyncio.timeout(timeout_seconds)

    async def __aenter__(self) -> Self:
        await self._timeout.__aenter__()
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        return await self._timeout.__aexit__(exception_type, exception, traceback)

    def renew(self) -> None:
        """Reset the deadline to the configured duration from now."""

        event_loop = asyncio.get_running_loop()
        self._timeout.reschedule(event_loop.time() + self._timeout_seconds)

    def when(self) -> float | None:
        """Return the current absolute event-loop deadline."""

        return self._timeout.when()

    def expired(self) -> bool:
        """Return whether the timeout has expired."""

        return self._timeout.expired()
