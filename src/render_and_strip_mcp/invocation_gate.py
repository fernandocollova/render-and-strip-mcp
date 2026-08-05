"""Application-level concurrency control for browser-agent sessions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager


class InvocationGate:
    """Gate browser sessions when a positive concurrency limit is configured."""

    def __init__(self, maximum_concurrent_invocations: int):
        self._semaphore = (
            asyncio.Semaphore(maximum_concurrent_invocations)
            if maximum_concurrent_invocations > 0
            else None
        )

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[None]:
        """Wait for a session slot or proceed immediately when concurrency is unlimited."""

        if self._semaphore is None:
            yield
            return
        await self._semaphore.acquire()
        try:
            yield
        finally:
            self._semaphore.release()
