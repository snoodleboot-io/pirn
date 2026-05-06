"""``DeltaTable`` — :class:`LakehouseTable` adapter over ``deltalake``.

Wraps the Rust-backed `deltalake` Python binding and exposes pirn's
:class:`LakehouseTable` interface. The vendor SDK is imported lazily at
construction / per-call time so importing this module does not require
``deltalake`` to be installed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
from typing import Any

from pirn.domains.data.lakehouse.delta.delta_table_config import DeltaTableConfig
from pirn.domains.data.lakehouse.lakehouse_table import LakehouseTable


class DeltaTable(LakehouseTable):
    """Delta Lake table adapter.

    Either pass a :class:`DeltaTableConfig` (production path; the table
    is opened lazily on first use), or inject a pre-built
    ``deltalake.DeltaTable`` via the ``dt=`` keyword for tests.
    """

    def __init__(
        self,
        config: DeltaTableConfig | None = None,
        *,
        dt: Any = None,
    ) -> None:
        if config is None and dt is None:
            raise TypeError("DeltaTable requires either config= or dt= (injected vendor table)")
        if config is not None and not isinstance(config, DeltaTableConfig):
            raise TypeError("DeltaTable: config must be a DeltaTableConfig instance")
        if config is not None and not config.table_uri:
            raise ValueError("DeltaTable: config.table_uri must be a non-empty string")
        self._config = config
        self._dt = dt
        self._closed = False

    @property
    def name(self) -> str:
        if self._config is not None and self._config.table_uri:
            return self._config.table_uri
        return "<test-injected>"

    async def scan(
        self,
        *,
        snapshot_id: int | str | None = None,
        as_of_timestamp: datetime | None = None,
        filter: Mapping[str, Any] | None = None,
        columns: Sequence[str] | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        dt = self._ensure_dt()
        if snapshot_id is not None and as_of_timestamp is not None:
            raise ValueError(
                "DeltaTable.scan: snapshot_id and as_of_timestamp are mutually exclusive"
            )
        if snapshot_id is not None:
            dt.load_as_version(int(snapshot_id))
        elif as_of_timestamp is not None:
            dt.load_with_datetime(as_of_timestamp)

        partitions = self._build_partitions(filter)
        kwargs: dict[str, Any] = {}
        if partitions is not None:
            kwargs["partitions"] = partitions
        if columns is not None:
            kwargs["columns"] = list(columns)
        table = dt.to_pyarrow_table(**kwargs)
        rows = table.to_pylist()

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            for row in rows:
                yield row

        return _iter()

    async def append(
        self,
        records: AsyncIterator[Mapping[str, Any]],
    ) -> str:
        pa = self._import_pyarrow()
        write_deltalake = self._import_write_deltalake()
        rows = await self._drain(records)
        table = pa.Table.from_pylist(rows)
        target = self._write_target()
        write_deltalake(
            target,
            table,
            mode="append",
            storage_options=self._storage_options(),
        )
        dt = self._reload_dt()
        return str(dt.version())

    async def overwrite(
        self,
        records: AsyncIterator[Mapping[str, Any]],
        *,
        partition_filter: Mapping[str, Any] | None = None,
    ) -> str:
        pa = self._import_pyarrow()
        write_deltalake = self._import_write_deltalake()
        rows = await self._drain(records)
        table = pa.Table.from_pylist(rows)
        target = self._write_target()
        kwargs: dict[str, Any] = {
            "mode": "overwrite",
            "storage_options": self._storage_options(),
        }
        predicate = self._partition_predicate(partition_filter)
        if predicate is not None:
            kwargs["predicate"] = predicate
        write_deltalake(target, table, **kwargs)
        dt = self._reload_dt()
        return str(dt.version())

    async def merge(
        self,
        records: AsyncIterator[Mapping[str, Any]],
        *,
        on: Sequence[str],
    ) -> str:
        if not on:
            raise ValueError("DeltaTable.merge: on must be a non-empty sequence")
        pa = self._import_pyarrow()
        rows = await self._drain(records)
        table = pa.Table.from_pylist(rows)
        dt = self._ensure_dt()
        predicate = " AND ".join(f"target.{key} = source.{key}" for key in on)
        builder = dt.merge(
            source=table,
            predicate=predicate,
            source_alias="source",
            target_alias="target",
        )
        builder = builder.when_matched_update_all().when_not_matched_insert_all()
        builder.execute()
        return str(dt.version())

    async def history(self) -> AsyncIterator[Mapping[str, Any]]:
        dt = self._ensure_dt()
        commits = list(dt.history())

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            for commit in commits:
                yield commit

        return _iter()

    async def close(self) -> None:
        self._dt = None
        self._closed = True
        self._clear_credentials()

    # ─────────────────────────────────────────────────────── helpers

    def _ensure_dt(self) -> Any:
        if self._closed:
            raise RuntimeError("DeltaTable is closed")
        if self._dt is not None:
            return self._dt
        sdk = self._import_deltalake()
        if self._config is None or not self._config.table_uri:
            raise RuntimeError("DeltaTable: missing config.table_uri and no injected dt")
        self._dt = sdk.DeltaTable(
            self._config.table_uri,
            storage_options=self._storage_options(),
        )
        return self._dt

    def _reload_dt(self) -> Any:
        # After a write, the in-memory table state is stale; reload from
        # storage if we own the SDK handle. If a test-injected dt is in
        # use, just return it.
        if self._dt is None:
            return self._ensure_dt()
        update_fn = getattr(self._dt, "update_incremental", None)
        if callable(update_fn):
            update_fn()
        return self._dt

    def _write_target(self) -> Any:
        # Prefer the SDK handle so the same table identity (and its
        # storage_options) is reused. Fall back to the URI string when
        # only a config is available.
        if self._dt is not None:
            return self._dt
        if self._config is None or not self._config.table_uri:
            raise RuntimeError("DeltaTable: missing config.table_uri and no injected dt")
        return self._config.table_uri

    def _storage_options(self) -> dict[str, str]:
        if self._config is None:
            return {}
        return dict(self._config.storage_options or {})

    @staticmethod
    def _build_partitions(
        filter: Mapping[str, Any] | None,
    ) -> list[tuple[str, str, Any]] | None:
        if not filter:
            return None
        return [(key, "=", value) for key, value in filter.items()]

    @staticmethod
    def _partition_predicate(
        partition_filter: Mapping[str, Any] | None,
    ) -> str | None:
        if not partition_filter:
            return None
        return " AND ".join(f"{key} = '{value}'" for key, value in partition_filter.items())

    @staticmethod
    async def _drain(
        records: AsyncIterator[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        async for record in records:
            rows.append(dict(record))
        return rows

    @staticmethod
    def _import_deltalake() -> Any:
        try:
            import deltalake  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "DeltaTable requires the 'deltalake' package. Install via "
                "`pip install pirn[delta]`."
            ) from exc
        return deltalake

    @staticmethod
    def _import_write_deltalake() -> Any:
        try:
            from deltalake import write_deltalake  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "DeltaTable requires the 'deltalake' package. Install via "
                "`pip install pirn[delta]`."
            ) from exc
        return write_deltalake

    @staticmethod
    def _import_pyarrow() -> Any:
        try:
            import pyarrow as pa
        except ImportError as exc:
            raise ImportError(
                "DeltaTable requires pyarrow. Install via "
                "`pip install pirn[data]` or `pip install pirn[delta]`."
            ) from exc
        return pa
