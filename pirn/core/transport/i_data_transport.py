"""``IDataTransport`` — pluggable data-movement layer between knots.

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
Individual knots can override the tapestry default via the reserved
``_transport=`` constructor kwarg. This is orthogonal to ``_config=``
and is injected by the executor, never read by knot code.

Lifecycle
---------
Each run produces a *run_id*. The executor calls :meth:`begin_run` once
before execution starts and :meth:`end_run` once after (success or
failure). Transports use these hooks to manage run-scoped resources
(e.g. creating and deleting a per-run temp directory).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pirn.core.transport.transport_handle import TransportHandle


class IDataTransport(ABC):
    """Abstract contract for all pirn data transports.

    Implementors are responsible for serialisation, storage, retrieval,
    and cleanup. The executor guarantees that :meth:`begin_run` is called
    before any :meth:`write` calls for a given *run_id*, and
    :meth:`end_run` is called exactly once per *run_id* when execution
    completes (regardless of success or failure).
    """

    @property
    @abstractmethod
    def transport_id(self) -> str:
        """Stable identifier for this transport instance.

        Stored in every :class:`~pirn.core.transport.transport_handle.TransportHandle`
        produced by this transport. Used by the executor to route reads
        back to the correct backend.
        """

    @abstractmethod
    async def begin_run(self, run_id: str) -> None:
        """Called once before any writes for *run_id*.

        Use for allocating run-scoped resources (e.g. creating a temp
        directory, acquiring a connection, recording a manifest entry).
        """

    @abstractmethod
    async def write(self, run_id: str, knot_id: str, value: Any) -> TransportHandle:
        """Persist *value* and return a handle that can retrieve it.

        Parameters
        ----------
        run_id:
            Identifier of the current execution run. Scopes the write
            so concurrent runs do not collide.
        knot_id:
            Identifier of the knot whose output is being stored. Used
            to construct a deterministic storage key.
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

    @abstractmethod
    async def read(self, handle: TransportHandle) -> Any:
        """Retrieve and return the value referenced by *handle*.

        Raises
        ------
        TransportError
            If the value cannot be retrieved (missing, corrupted, expired).
        """

    @abstractmethod
    async def exists(self, handle: TransportHandle) -> bool:
        """Return True if the value referenced by *handle* is still available."""

    @abstractmethod
    async def end_run(self, run_id: str, *, success: bool) -> None:
        """Called once after execution of *run_id* finishes.

        Parameters
        ----------
        run_id:
            The run whose resources should be released.
        success:
            True if the run completed without errors. Transports may
            choose to retain data on failure for debugging.

        Raises
        ------
        TransportError
            If cleanup fails. The executor logs but does not re-raise
            cleanup failures so that the run result is not obscured.
        """
