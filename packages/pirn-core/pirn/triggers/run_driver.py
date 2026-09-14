"""``RunDriver`` — shared iterate/convert/run/observe loop.

``triggers.trigger.run_forever`` and ``streaming.streaming_source.run_stream``
were near-identical module-level drivers: pull one event at a time from an
async iterator, convert it to a ``RunRequest``, run it against a
``Tapestry``, dispatch the result (or an unhandled exception) to an optional
callback, and always close the underlying source on exit. ``RunDriver``
factors that loop out; both public functions become thin wrappers that
supply the two things that differ — how an event becomes a ``RunRequest``,
and what "close" means for their event source.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pirn.core.run_request import RunRequest
    from pirn.core.run_result import RunResult
    from pirn.tapestry import Tapestry

_logger = logging.getLogger(__name__)


class RunDriver:
    """Stateless driver shared by ``Trigger.run_forever`` and ``StreamingSource.run_stream``."""

    @staticmethod
    async def drive(
        events: AsyncIterator[Any],
        *,
        tapestry: Tapestry,
        to_request: Callable[[Any], RunRequest],
        close: Callable[[], Awaitable[None]],
        close_error_context: str,
        on_result: Callable[[Any, RunResult], Awaitable[None]] | None = None,
        on_error: Callable[[Any, BaseException], Awaitable[None]] | None = None,
    ) -> None:
        """Pull events, run each as a request, observe the outcome, always close.

        Args:
            events: Async iterator of raw events (a ``RunRequest`` for
                triggers, an arbitrary value for streaming sources).
            tapestry: The tapestry each request runs against.
            to_request: Converts one event into the ``RunRequest`` to run.
            close: Awaited exactly once, in a ``finally``, regardless of how
                the loop ends (exhaustion, cancellation, or an unhandled
                error re-raised past ``on_error``).
            close_error_context: Short description of what ``close`` does,
                used only in the warning logged if it raises.
            on_result: Awaited with ``(event, result)`` after a successful run.
            on_error: Awaited with ``(event, exc)`` after a failed run,
                instead of re-raising it. ``asyncio.CancelledError``,
                ``KeyboardInterrupt`` and ``SystemExit`` always re-raise
                before ``on_error`` is consulted — they end the process
                rather than describe a bad event, so a log-and-continue
                observer must not be able to swallow them and leave the
                loop running after its task was cancelled.
        """
        try:
            async for event in events:
                request = to_request(event)
                try:
                    result = await tapestry.run(request)
                except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
                    raise
                except BaseException as exc:
                    if on_error is not None:
                        await on_error(event, exc)
                    else:
                        raise
                else:
                    if on_result is not None:
                        await on_result(event, result)
        finally:
            try:
                await close()
            except Exception:
                _logger.warning(
                    "RunDriver: %s raised while shutting down",
                    close_error_context,
                    exc_info=True,
                )
