"""Trigger protocol and runtime helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from pirn.triggers.run_driver import RunDriver

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pirn.core.run_request import RunRequest
    from pirn.core.run_result import RunResult
    from pirn.tapestry import Tapestry


# Type aliases for the optional callbacks.
_OnResult = Callable[["RunRequest", "RunResult"], Awaitable[None]]
_OnError = Callable[["RunRequest", BaseException], Awaitable[None]]


class Trigger:
    """Yields ``RunRequest``s as external events arrive.

    Implementations are async generators.  They open whatever
    connection they need (Kafka consumer, HTTP server, cron schedule),
    and yield a fresh ``RunRequest`` for each event.

    The runtime drives the trigger by calling
    ``trigger.run_forever(tapestry)``, which consumes requests and calls
    ``tapestry.run`` for each.
    """

    @property
    def name(self) -> str:
        """Human-readable identifier for this trigger, used in logs and error messages."""
        raise NotImplementedError(f"{type(self).__name__} must implement name")

    def stream(self) -> AsyncIterator[RunRequest]:
        """Yield ``RunRequest`` objects as external events arrive.

        Implementations are async generators that open their underlying
        connection (Kafka consumer, HTTP server, cron schedule) and yield
        one ``RunRequest`` per event.  The generator should respect
        cancellation by exiting cleanly when the enclosing task is
        cancelled.

        Returns:
            An async iterator of ``RunRequest`` objects.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement stream()")

    async def close(self) -> None:
        """Release resources and stop the trigger.

        Called by :meth:`run_forever` on exit (cancellation, error, or
        normal stream end).  Implementations must be idempotent.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement close()")

    async def run_forever(
        self,
        tapestry: Tapestry,
        *,
        on_result: _OnResult | None = None,
        on_error: _OnError | None = None,
    ) -> None:
        """Drive a trigger: pull requests, run them, optionally observe.

        Calls :meth:`close` on exit (on cancellation, error, or
        normal stream end).  ``on_result`` and ``on_error`` are optional
        callbacks; they're awaited if present.

        Cancellation is the standard async pattern: the caller can wrap
        this coroutine in a task and ``task.cancel()`` it.

        ``on_error`` observes *run failures* only.  ``asyncio.CancelledError``,
        ``KeyboardInterrupt`` and ``SystemExit`` are re-raised before it is
        consulted: they end the process rather than describe a bad event, so a
        log-and-continue observer — the obvious thing to write for a daemon —
        must not be able to swallow them and leave the loop running after its
        task was cancelled.

        Thin wrapper around ``RunDriver.drive``, shared with
        ``StreamingSource.run_stream``: a trigger's events already
        are ``RunRequest``s, so ``to_request`` is the identity function, and
        "close" means :meth:`close`.
        """
        await RunDriver.drive(
            self.stream(),
            tapestry=tapestry,
            to_request=lambda request: request,
            close=self.close,
            close_error_context="trigger.close()",
            on_result=on_result,
            on_error=on_error,
        )
