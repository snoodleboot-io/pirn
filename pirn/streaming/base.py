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

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pirn.core.context import RunResult
    from pirn.tapestry import Tapestry


# Type aliases for callbacks.
_OnResult = Callable[[Any, "RunResult"], Awaitable[None]]
_OnError = Callable[[Any, BaseException], Awaitable[None]]


@runtime_checkable
class StreamingSource(Protocol):
    """Yields a sequence of values over time.

    Each yielded value gets bound to the parameter named ``parameter_name``
    of the runs the driver kicks off.  When the source is exhausted the
    driver exits.
    """

    @property
    def name(self) -> str: ...

    @property
    def parameter_name(self) -> str:
        """The parameter name that downstream knots consume."""
        ...

    def stream(self) -> AsyncIterator[Any]: ...

    async def close(self) -> None: ...


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
    """
    from pirn.core.context import RunRequest

    base_params = dict(extra_parameters or {})
    try:
        async for value in source.stream():
            params = dict(base_params)
            params[source.parameter_name] = value
            request = RunRequest(parameters=params)
            try:
                result = await tapestry.run(request)
            except BaseException as exc:
                if on_error is not None:
                    await on_error(value, exc)
                else:
                    raise
            else:
                if on_result is not None:
                    await on_result(value, result)
    finally:
        try:
            await source.close()
        except Exception:
            pass
