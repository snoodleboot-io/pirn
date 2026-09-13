"""Streaming source protocol and the run_stream driver.

A streaming source is *like* a knot in that it produces values for
downstream knots, but its lifecycle is different: it produces multiple
values over time, and the engine ticks the downstream graph once per
value.

Implementation note: rather than treating a ``StreamingSource`` as a
true ``Knot`` and complicating the engine, we expose it as a separate
abstraction with a dedicated driver (``run_stream``).  The driver
takes the source plus a list of downstream terminal knots; for each
value the source emits, it runs the terminals (treating the source's
value as a parameter binding).

This keeps the request/response engine simple and the streaming engine
focused.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from pirn.triggers._run_driver import _RunDriver

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pirn.core.run_request import RunRequest
    from pirn.core.run_result import RunResult
    from pirn.tapestry import Tapestry


# Type aliases for callbacks.
_OnResult = Callable[[Any, "RunResult"], Awaitable[None]]
_OnError = Callable[[Any, BaseException], Awaitable[None]]


class StreamingSource:
    """Yields a sequence of values over time.

    Each yielded value gets bound to the parameter named ``parameter_name``
    of the runs the driver kicks off.  When the source is exhausted the
    driver exits.
    """

    @property
    def name(self) -> str:
        raise NotImplementedError(f"{type(self).__name__} must implement name")

    @property
    def parameter_name(self) -> str:
        """The parameter name that downstream knots consume."""
        raise NotImplementedError(f"{type(self).__name__} must implement parameter_name")

    def stream(self) -> AsyncIterator[Any]:
        raise NotImplementedError(f"{type(self).__name__} must implement stream()")

    async def close(self) -> None:
        raise NotImplementedError(f"{type(self).__name__} must implement close()")


def _bind_stream_value(base_params: dict[str, Any], parameter_name: str, value: Any) -> RunRequest:
    """Build the ``RunRequest`` for one streamed ``value``.

    Module-level (not a closure) so ``run_stream`` can bind ``base_params``
    and ``parameter_name`` via ``functools.partial`` instead of nesting a
    function that captures them.
    """
    from pirn.core.run_request import RunRequest

    params = dict(base_params)
    params[parameter_name] = value
    return RunRequest(parameters=params)


async def run_stream(
    source: StreamingSource,
    tapestry: Tapestry,
    *,
    on_result: _OnResult | None = None,
    on_error: _OnError | None = None,
    extra_parameters: dict[str, Any] | None = None,
) -> None:
    """Drive a streaming source against a tapestry.

    For each value the source yields, kick off a run with that value
    bound to ``source.parameter_name`` (plus any ``extra_parameters``
    that should also be available each tick).

    The driver runs until the source's stream is exhausted, or until
    cancellation.  ``source.close()`` is called on exit.

    Compared to ``triggers.run_forever``: triggers build a full
    ``RunRequest`` per event (they're independent jobs), whereas this
    driver inlines a single parameter from the source — implying the
    source is the *primary* input and other parameters are constants
    for the run.

    Thin wrapper around ``_RunDriver.drive``, shared with
    ``triggers.trigger.run_forever``: ``to_request`` binds each value to
    ``source.parameter_name`` alongside ``extra_parameters``, and "close"
    means ``source.close()``. A cancelled run ends the stream; it is not a
    bad value for ``on_error`` to log and skip past (PIR-841) — see the
    ``asyncio.CancelledError`` re-raise inside ``_RunDriver.drive``.
    """
    base_params = dict(extra_parameters or {})
    to_request = functools.partial(_bind_stream_value, base_params, source.parameter_name)

    await _RunDriver.drive(
        source.stream(),
        tapestry=tapestry,
        to_request=to_request,
        close=source.close,
        close_error_context="source.close()",
        on_result=on_result,
        on_error=on_error,
    )
