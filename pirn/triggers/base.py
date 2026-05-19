"""Trigger protocol and runtime helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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

    The runtime drives the trigger by calling ``run_forever(trigger,
    tapestry)``; that helper consumes requests and calls
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

        Called by ``run_forever`` on exit (cancellation, error, or
        normal stream end).  Implementations must be idempotent.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement close()")


async def run_forever(
    trigger: Trigger,
    tapestry: Tapestry,
    *,
    on_result: _OnResult | None = None,
    on_error: _OnError | None = None,
) -> None:
    """Drive a trigger: pull requests, run them, optionally observe.

    Calls ``trigger.close()`` on exit (on cancellation, error, or
    normal stream end).  ``on_result`` and ``on_error`` are optional
    callbacks; they're awaited if present.

    Cancellation is the standard async pattern: the caller can wrap
    this coroutine in a task and ``task.cancel()`` it.
    """
    try:
        async for request in trigger.stream():
            try:
                result = await tapestry.run(request)
            except BaseException as exc:
                if on_error is not None:
                    await on_error(request, exc)
                else:
                    raise
            else:
                if on_result is not None:
                    await on_result(request, result)
    finally:
        try:
            await trigger.close()
        except Exception:
            pass
