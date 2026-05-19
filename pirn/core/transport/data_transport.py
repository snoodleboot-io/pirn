"""``DataTransport`` — pluggable data-movement layer between knots.

Every edge in a pirn knot graph has a transport. The transport decides
where a knot's output lives between when the upstream knot produces it
and when the downstream knot consumes it. The executing framework
(not the knots themselves) calls :meth:`write` and :meth:`read`;
knot ``process()`` methods always see fully-materialised Python values.

Pass 1 — tapestry-level transport
----------------------------------
A single transport instance is set on the ``Tapestry`` and applies to
every edge:

    with Tapestry(transport=FilesystemTransport(base_dir="/tmp/pirn")) as t:
        ...

Pass 2 — per-knot override
---------------------------
Individual knots can override the tapestry default via ``KnotConfig.transport``.
This is injected by the executor and is never read by knot code.

Lifecycle
---------
Each run produces a *run_id*. The executor calls :meth:`begin_run` once
before execution starts and :meth:`end_run` once after (success or
failure). Transports use these hooks to manage run-scoped resources
(e.g. creating and deleting a per-run temp directory).
"""

from __future__ import annotations

from typing import Any

from pirn.core.transport.transport_handle import TransportHandle


class DataTransport:
    """Base class for all pirn data transports.

    Subclass and override all methods. The executor guarantees that
    :meth:`begin_run` is called before any :meth:`write` calls for a
    given *run_id*, and :meth:`end_run` is called exactly once per
    *run_id* when execution completes (regardless of success or failure).
    """

    @property
    def transport_id(self) -> str:
        """Stable identifier for this transport instance.

        Stored in every :class:`~pirn.core.transport.transport_handle.TransportHandle`
        produced by this transport.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement transport_id")

    async def begin_run(self, run_id: str) -> None:
        """Called once before any writes for *run_id*.

        Use for allocating run-scoped resources (e.g. creating a temp
        directory, acquiring a connection, recording a manifest entry).
        """
        raise NotImplementedError(f"{type(self).__name__} must implement begin_run()")

    async def write(self, run_id: str, knot_id: str, value: Any) -> TransportHandle:
        """Persist *value* and return a handle that can retrieve it.

        Parameters
        ----------
        run_id:
            Identifier of the current execution run.
        knot_id:
            Identifier of the knot whose output is being stored.
        value:
            The fully-materialised output of a knot's ``process()`` call.

        Returns
        -------
        TransportHandle
            Lightweight token the executor caches in place of *value*.

        Raises
        ------
        TransportError
            If the write cannot complete.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement write()")

    async def read(self, handle: TransportHandle) -> Any:
        """Retrieve and return the value referenced by *handle*.

        Raises
        ------
        TransportError
            If the value cannot be retrieved (missing, corrupted, expired).
        """
        raise NotImplementedError(f"{type(self).__name__} must implement read()")

    async def exists(self, handle: TransportHandle) -> bool:
        """Return True if the value referenced by *handle* is still available."""
        raise NotImplementedError(f"{type(self).__name__} must implement exists()")

    async def end_run(self, run_id: str, *, success: bool) -> None:
        """Called once after execution of *run_id* finishes.

        Parameters
        ----------
        run_id:
            The run whose resources should be released.
        success:
            True if the run completed without errors.

        Raises
        ------
        TransportError
            If cleanup fails.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement end_run()")
