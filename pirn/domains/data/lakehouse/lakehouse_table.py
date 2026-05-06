"""``LakehouseTable`` — versioned, transactional table interface.

Lakehouse table formats (Delta Lake, Apache Iceberg, Apache Hudi) are
**not** file formats. They are table specs with:

* transaction logs,
* schema evolution,
* time travel (snapshot id / timestamp queries),
* partition pruning,
* compaction.

Forcing them through :class:`FileFormat` (single-file encode/decode)
loses every distinguishing feature. This interface is the proper
abstraction.

Concrete implementations live under ``delta/``, ``iceberg/``, and
``hudi/`` sub-packages; each wraps the relevant vendor SDK
(``deltalake``, ``pyiceberg``, ``hudi-python``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class LakehouseTable(PirnOpaqueValue):
    """Interface every lakehouse table implementation must satisfy."""

    @property
    def name(self) -> str:
        """Table identifier."""
        raise NotImplementedError(f"{type(self).__name__} must implement name")

    async def scan(
        self,
        *,
        snapshot_id: int | str | None = None,
        as_of_timestamp: datetime | None = None,
        filter: Mapping[str, Any] | None = None,
        columns: Sequence[str] | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Yield rows.

        ``snapshot_id`` selects a specific committed version; mutually
        exclusive with ``as_of_timestamp`` (time-travel).

        ``filter`` is a vendor-translated row filter (Iceberg / Delta
        push the predicate down to the file scan).

        ``columns`` projects only the named columns. ``None`` returns
        all columns.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement scan()")

    async def append(
        self,
        records: AsyncIterator[Mapping[str, Any]],
    ) -> str:
        """Insert ``records`` as a new commit. Returns the new
        snapshot id (as a string for vendor consistency)."""
        raise NotImplementedError(f"{type(self).__name__} must implement append()")

    async def overwrite(
        self,
        records: AsyncIterator[Mapping[str, Any]],
        *,
        partition_filter: Mapping[str, Any] | None = None,
    ) -> str:
        """Replace the entire table (or a partition slice) with
        ``records``. Returns the new snapshot id."""
        raise NotImplementedError(f"{type(self).__name__} must implement overwrite()")

    async def merge(
        self,
        records: AsyncIterator[Mapping[str, Any]],
        *,
        on: Sequence[str],
    ) -> str:
        """MERGE-style upsert: rows whose ``on`` keys exist are updated,
        new keys are inserted. Returns the new snapshot id."""
        raise NotImplementedError(f"{type(self).__name__} must implement merge()")

    async def history(self) -> AsyncIterator[Mapping[str, Any]]:
        """Yield commit history (snapshot id, timestamp, operation,
        committer, metrics)."""
        raise NotImplementedError(f"{type(self).__name__} must implement history()")

    async def close(self) -> None:
        """Release any underlying SDK / connection resources."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")

    def _clear_credentials(self) -> None:
        """Drop in-memory credentials. Concrete implementations call
        from ``close()``. Default nulls ``self._config``; override if
        your implementation uses different field names."""
        if hasattr(self, "_config"):
            self._config = None
