"""``connector_lifespan`` — deterministic close/teardown for pooled connectors.

The F16 connectors hold live pooled backend clients, so a run that vends them
must release them when it finishes — on success *or* on error. This async
context manager guarantees exactly that: it yields the connectors it was given
and, on exit, closes each one in reverse order regardless of whether the body
raised. Any object exposing a ``close`` attribute is handled (sync or async), so
the same helper covers HTTP, SQL, search, and storage connectors uniformly.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any


class ConnectorLifespan:
    """Namespace for the pooled-connector teardown context manager."""

    @staticmethod
    @asynccontextmanager
    async def manage(*connectors: Any) -> AsyncIterator[tuple[Any, ...]]:
        """Yield ``connectors`` and deterministically close them all on exit.

        Args:
            *connectors: The pooled connectors to manage for the run.

        Yields:
            The same connectors as a tuple, for convenient unpacking.

        The connectors are closed in reverse construction order in a
        ``finally`` so a raised exception still tears every pooled client
        down; each connector's error during close is suppressed after the
        others are closed so one failure cannot leak the rest.
        """
        try:
            yield connectors
        finally:
            errors: list[BaseException] = []
            for connector in reversed(connectors):
                closer = getattr(connector, "close", None)
                if not callable(closer):
                    continue
                try:
                    result = closer()
                    if inspect.isawaitable(result):
                        await result
                except BaseException as exc:
                    errors.append(exc)
            if errors:
                raise errors[0]


def connector_lifespan(*connectors: Any) -> AbstractAsyncContextManager[tuple[Any, ...]]:
    """Yield ``connectors`` and deterministically close them all on exit.

    Thin wrapper kept for the pinned public import path (see
    ``tests/test_ws5_s1_import_surface.py``); see :meth:`ConnectorLifespan.manage`.
    """
    return ConnectorLifespan.manage(*connectors)
