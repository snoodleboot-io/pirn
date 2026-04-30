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
        raise NotImplementedError(f"{type(self).__name__} must implement name")

    def stream(self) -> AsyncIterator[RunRequest]:
        raise NotImplementedError(f"{type(self).__name__} must implement stream()")

    async def close(self) -> None:
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
