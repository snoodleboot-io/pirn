"""``IcebergTable`` — :class:`LakehouseTable` adapter over ``pyiceberg``.

Wraps a ``pyiceberg.table.Table`` and exposes pirn's
:class:`LakehouseTable` interface. The vendor SDK is imported lazily so
importing this module does not require ``pyiceberg``.

Note
----
``pyiceberg`` (>=0.6) does not yet ship a native MERGE primitive in
its Python writer; :meth:`merge` raises :class:`NotImplementedError`
with a pointer to the issue. Implementing MERGE on top of the public
``append`` / ``delete`` API is possible but is out of scope for this
adapter — the Java/Scala writer should be used until the Python
writer reaches parity.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
from typing import Any

from pirn.domains.data.lakehouse.iceberg.iceberg_table_config import (
    IcebergTableConfig,
)
from pirn.domains.data.lakehouse.lakehouse_table import LakehouseTable


class IcebergTable(LakehouseTable):
    """Iceberg table adapter.

    Either pass an :class:`IcebergTableConfig` (production path; the
    table is resolved from the named catalog on first use), or inject a
    pre-built ``pyiceberg.table.Table`` via the ``table=`` keyword for
    tests.
    """

    def __init__(
        self,
        config: IcebergTableConfig | None = None,
        *,
        table: Any = None,
    ) -> None:
        if config is None and table is None:
            raise TypeError(
                "IcebergTable requires either config= or table= (injected pyiceberg.table.Table)"
            )
        if config is not None and not isinstance(config, IcebergTableConfig):
            raise TypeError("IcebergTable: config must be an IcebergTableConfig instance")
        if config is not None and not config.table_identifier:
            raise ValueError("IcebergTable: config.table_identifier must be a non-empty string")
        self._config = config
        self._table = table
        self._closed = False

    @property
    def name(self) -> str:
        if self._config is not None and self._config.table_identifier:
            return self._config.table_identifier
        return "<test-injected>"

    async def scan(
        self,
        *,
        snapshot_id: int | str | None = None,
        as_of_timestamp: datetime | None = None,
        filter: Mapping[str, Any] | None = None,
        columns: Sequence[str] | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        if snapshot_id is not None and as_of_timestamp is not None:
            raise ValueError(
                "IcebergTable.scan: snapshot_id and as_of_timestamp are mutually exclusive"
            )
        table = self._ensure_table()
        scan_kwargs: dict[str, Any] = {}
        if snapshot_id is not None:
            scan_kwargs["snapshot_id"] = int(snapshot_id)
        elif as_of_timestamp is not None:
            scan_kwargs["snapshot_id"] = self._snapshot_for_timestamp(table, as_of_timestamp)
        if filter is not None:
            scan_kwargs["row_filter"] = self._row_filter_expression(filter)
        if columns is not None:
            scan_kwargs["selected_fields"] = tuple(columns)
        scanner = table.scan(**scan_kwargs)
        rows = scanner.to_arrow().to_pylist()

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            for row in rows:
                yield row

        return _iter()

    async def append(
        self,
        records: AsyncIterator[Mapping[str, Any]],
    ) -> str:
        pa = self._import_pyarrow()
        rows = await self._drain(records)
        pa_table = pa.Table.from_pylist(rows)
        table = self._ensure_table()
        table.append(pa_table)
        return self._current_snapshot_id(table)

    async def overwrite(
        self,
        records: AsyncIterator[Mapping[str, Any]],
        *,
        partition_filter: Mapping[str, Any] | None = None,
    ) -> str:
        pa = self._import_pyarrow()
        rows = await self._drain(records)
        pa_table = pa.Table.from_pylist(rows)
        table = self._ensure_table()
        kwargs: dict[str, Any] = {}
        overwrite_filter = self._row_filter_expression(partition_filter)
        if overwrite_filter is not None:
            kwargs["overwrite_filter"] = overwrite_filter
        table.overwrite(pa_table, **kwargs)
        return self._current_snapshot_id(table)

    async def merge(
        self,
        records: AsyncIterator[Mapping[str, Any]],
        *,
        on: Sequence[str],
    ) -> str:
        raise NotImplementedError(
            "IcebergTable.merge requires manual upsert via append + delete; "
            "pyiceberg native MERGE pending. Use the Java/Scala writer or a "
            "pirn merge-knot composition until the Python writer adds MERGE."
        )

    async def history(self) -> AsyncIterator[Mapping[str, Any]]:
        table = self._ensure_table()
        commits = list(table.history())

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            for commit in commits:
                yield self._history_entry(commit)

        return _iter()

    async def close(self) -> None:
        self._table = None
        self._closed = True
        self._clear_credentials()

    # ─────────────────────────────────────────────────────── helpers

    def _ensure_table(self) -> Any:
        if self._closed:
            raise RuntimeError("IcebergTable is closed")
        if self._table is not None:
            return self._table
        catalog_module = self._import_pyiceberg_catalog()
        if self._config is None or not self._config.table_identifier:
            raise RuntimeError(
                "IcebergTable: missing config.table_identifier and no injected table"
            )
        catalog = catalog_module.load_catalog(
            self._config.catalog_name,
            **dict(self._config.catalog_properties or {}),
        )
        self._table = catalog.load_table(self._config.table_identifier)
        return self._table

    @staticmethod
    def _snapshot_for_timestamp(table: Any, ts: datetime) -> int:
        # pyiceberg exposes time-travel via snapshot id; map a timestamp
        # to the most recent snapshot at-or-before ``ts`` from the
        # table's history.
        millis = int(ts.timestamp() * 1000)
        chosen: int | None = None
        for entry in table.history():
            ts_ms = getattr(entry, "timestamp_ms", None)
            snap_id = getattr(entry, "snapshot_id", None)
            if ts_ms is None or snap_id is None:
                continue
            if ts_ms <= millis:
                chosen = int(snap_id)
        if chosen is None:
            raise ValueError(f"IcebergTable.scan: no snapshot at or before timestamp {ts!r}")
        return chosen

    @staticmethod
    def _row_filter_expression(
        filter: Mapping[str, Any] | None,
    ) -> Any | None:
        if not filter:
            return None
        # Build a pyiceberg expression: AND of EqualTo predicates.
        try:
            from pyiceberg.expressions import (  # type: ignore[import-not-found]
                And,
                EqualTo,
            )
        except ImportError as exc:
            raise ImportError(
                "IcebergTable filter pushdown requires pyiceberg. Install via "
                "`pip install pirn[iceberg]`."
            ) from exc
        items = list(filter.items())
        expr = EqualTo(items[0][0], items[0][1])
        for key, value in items[1:]:
            expr = And(expr, EqualTo(key, value))
        return expr

    @staticmethod
    def _current_snapshot_id(table: Any) -> str:
        snapshot = table.current_snapshot()
        if snapshot is None:
            raise RuntimeError(
                "IcebergTable: no current snapshot after write — vendor SDK returned None"
            )
        return str(snapshot.snapshot_id)

    @staticmethod
    def _history_entry(commit: Any) -> Mapping[str, Any]:
        # pyiceberg history entries are namedtuples / models; expose the
        # common attributes as a plain mapping for downstream consumers.
        keys = ("snapshot_id", "timestamp_ms", "parent_snapshot_id", "operation")
        out: dict[str, Any] = {}
        for key in keys:
            if hasattr(commit, key):
                out[key] = getattr(commit, key)
        return out

    @staticmethod
    async def _drain(
        records: AsyncIterator[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        async for record in records:
            rows.append(dict(record))
        return rows

    @staticmethod
    def _import_pyiceberg_catalog() -> Any:
        try:
            from pyiceberg import catalog  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "IcebergTable requires the 'pyiceberg' package. Install via "
                "`pip install pirn[iceberg]`."
            ) from exc
        return catalog

    @staticmethod
    def _import_pyarrow() -> Any:
        try:
            import pyarrow as pa
        except ImportError as exc:
            raise ImportError(
                "IcebergTable requires pyarrow. Install via "
                "`pip install pirn[data]` or `pip install pirn[iceberg]`."
            ) from exc
        return pa
