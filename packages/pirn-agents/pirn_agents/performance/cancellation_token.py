"""``CancellationToken`` — cooperative cancellation signal for budgeted runs.

A single-writer, many-reader flag built on :class:`asyncio.Event`. A budget
meter (or any supervisor) flips it on breach; every cooperating coroutine
polls :meth:`raise_if_cancelled` at its checkpoints or awaits :meth:`wait` to
unblock the instant cancellation is requested. Cancellation is *cooperative*:
the token never force-kills a task, so there is no partial-state corruption —
callers observe the flag and unwind their own resources cleanly.
"""

from __future__ import annotations

import asyncio


class CancellationToken:
    """A latch that, once set, stays set and signals cooperative cancellation."""

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._reason: str | None = None

    @property
    def cancelled(self) -> bool:
        """Whether cancellation has been requested."""
        return self._event.is_set()

    @property
    def reason(self) -> str | None:
        """Human-readable reason recorded at :meth:`cancel` time, if any."""
        return self._reason

    def cancel(self, reason: str | None = None) -> None:
        """Request cancellation, recording ``reason`` on the first call only.

        Idempotent: subsequent calls neither clear the flag nor overwrite the
        first-recorded reason, so the originating cause survives.
        """
        if not self._event.is_set():
            self._reason = reason
            self._event.set()

    def raise_if_cancelled(self) -> None:
        """Raise :class:`asyncio.CancelledError` if cancellation was requested.

        The cooperative checkpoint: call it at loop boundaries so a breached
        budget unwinds through normal ``CancelledError`` propagation.
        """
        if self._event.is_set():
            raise asyncio.CancelledError(self._reason or "run cancelled")

    async def wait(self) -> None:
        """Block until cancellation is requested (returns immediately if already set)."""
        await self._event.wait()
