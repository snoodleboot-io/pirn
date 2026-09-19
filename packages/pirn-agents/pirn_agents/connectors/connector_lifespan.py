"""``ConnectorLifespan`` — deterministic close/teardown for pooled connectors.

The F16 connectors hold live pooled backend clients, so a run that vends them
must release them when it finishes — on success *or* on error. This async
context manager guarantees exactly that: it yields the connectors it was given
and, on exit, closes each one in reverse order regardless of whether the body
raised (``async with ConnectorLifespan.manage(a, b) as (a, b): ...``). Any
object exposing a ``close`` attribute is handled (sync or async), so the same
helper covers HTTP, SQL, search, and storage connectors uniformly.

What a close failure does (PIR-873). Teardown used to end in ``raise errors[0]``
inside the ``finally``, which did three wrong things: it dropped every close
error after the first, it *replaced* the body's exception — so a caller waiting
for its own failure saw a close error instead — and it caught ``BaseException``,
turning a ``CancelledError`` or ``KeyboardInterrupt`` arriving mid-close into a
"close error" that was then re-raised as if it were one. Now:

* only ``Exception`` is collected; a ``BaseException`` during a close is the
  process being torn down and propagates at once (the connectors after it are
  not closed, because nothing after it should run either);
* if the body raised, that exception still wins, and each close failure is
  attached to it as a note, so nothing is dropped and nothing is substituted;
* if the body succeeded, one close failure is raised as itself and several are
  raised together as an ``ExceptionGroup`` — never just the first.

Algorithm:
    1. Yield the connectors, remembering the body's exception if it raises.
    2. In a ``finally``, close every connector that has a callable ``close``,
       in reverse construction order, awaiting an awaitable result.
    3. Collect each close's ``Exception`` and carry on, so one failure cannot
       leak the remaining clients.
    4. Report the collected failures as described above.

References:
    [1] PEP 654 — Exception Groups: https://peps.python.org/pep-0654/
    [2] ``contextlib.AsyncExitStack``, whose unwinding order this mirrors:
        https://docs.python.org/3/library/contextlib.html
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any


class ConnectorLifespan:
    """Namespace for the pooled-connector teardown context manager."""

    @staticmethod
    @asynccontextmanager
    async def manage(*connectors: Any) -> AsyncGenerator[tuple[Any, ...], None]:
        """Yield ``connectors`` and deterministically close them all on exit.

        Args:
            *connectors: The pooled connectors to manage for the run.

        Yields:
            The same connectors as a tuple, for convenient unpacking.

        Raises:
            ExceptionGroup: If the body succeeded and more than one connector
                failed to close; the group holds every failure.
            Exception: If the body succeeded and exactly one connector failed to
                close, that failure itself. If the body raised, its own
                exception propagates instead, carrying a note per close failure.
        """
        body_error: BaseException | None = None
        try:
            yield connectors
        except BaseException as exc:
            body_error = exc
            raise
        finally:
            errors = await ConnectorLifespan._close_all(connectors)
            if errors:
                if body_error is not None:
                    for error in errors:
                        body_error.add_note(
                            f"connector close failed: {type(error).__name__}: {error}"
                        )
                elif len(errors) == 1:
                    raise errors[0]
                else:
                    raise ExceptionGroup("connector teardown failed", errors)

    @staticmethod
    async def _close_all(connectors: tuple[Any, ...]) -> list[Exception]:
        """Close every connector in reverse order; return the failures, in that order.

        Args:
            connectors: The connectors in construction order.

        Returns:
            One entry per connector whose ``close`` raised an ``Exception``.

        Raises:
            BaseException: Immediately, if a close raises one that is not an
                ``Exception`` — a cancellation or an interrupt is the process
                shutting down, not a connector fault, and must not be collected
                and re-raised as one.
        """
        errors: list[Exception] = []
        for connector in reversed(connectors):
            closer = getattr(connector, "close", None)
            if not callable(closer):
                continue
            try:
                result = closer()
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                errors.append(exc)
        return errors
