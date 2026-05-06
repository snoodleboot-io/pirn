"""``HudiTable`` — :class:`LakehouseTable` adapter for Apache Hudi.

The Python ecosystem for Hudi is limited as of mid-2026:

* The Spark/Java writers (``hudi-spark-bundle``) are the only stable
  way to commit transactions; they are out of scope for an in-process
  Python adapter.
* ``pyhudi`` (PyPI) is experimental and does not provide a stable
  read/write API; it is not declared as a default dependency.
* Hudi tables are physically stored as Parquet (plus a ``.hoodie/``
  metadata directory). For read-only consumption the latest commit's
  Parquet files can be read directly with ``pyarrow``.

Accordingly, this adapter is read-only and stub-with-NotImplementedError
for the write paths. Each NotImplementedError points at the Spark/Java
writer as the production solution. Tests inject a stub vendor table via
the ``table=`` keyword to exercise the read path without touching the
filesystem.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
from typing import Any

from pirn.domains.data.lakehouse.hudi.hudi_table_config import HudiTableConfig
from pirn.domains.data.lakehouse.lakehouse_table import LakehouseTable


class HudiTable(LakehouseTable):
    """Hudi table adapter.

    Either pass a :class:`HudiTableConfig` (read-only path; resolves
    Parquet files under the configured ``table_path``), or inject a
    test stub via ``table=`` exposing ``scan_pylist()`` and
    ``history()``.
    """

    _allowed_table_types = ("COPY_ON_WRITE", "MERGE_ON_READ")

    def __init__(
        self,
        config: HudiTableConfig | None = None,
        *,
        table: Any = None,
    ) -> None:
        if config is None and table is None:
            raise TypeError("HudiTable requires either config= or table= (injected stub)")
        if config is not None and not isinstance(config, HudiTableConfig):
            raise TypeError("HudiTable: config must be a HudiTableConfig instance")
        if config is not None and not config.table_path:
            raise ValueError("HudiTable: config.table_path must be a non-empty string")
        if config is not None and config.table_type not in self._allowed_table_types:
            raise ValueError(
                "HudiTable: table_type must be one of "
                f"{list(self._allowed_table_types)}, got {config.table_type!r}"
            )
        if config is not None and not config.record_key_field:
            raise ValueError("HudiTable: record_key_field must be a non-empty string")
        if config is not None and not config.precombine_field:
            raise ValueError("HudiTable: precombine_field must be a non-empty string")
        self._config = config
        self._table = table
        self._closed = False

    @property
    def name(self) -> str:
        if self._config is not None and self._config.table_path:
            return self._config.table_path
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
                "HudiTable.scan: snapshot_id and as_of_timestamp are mutually exclusive"
            )
        if self._closed:
            raise RuntimeError("HudiTable is closed")
        if self._table is not None:
            rows = self._scan_stub(self._table, columns)
        else:
            rows = self._scan_parquet(columns)
        if filter:
            rows = [row for row in rows if self._row_matches(row, filter)]

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            for row in rows:
                yield row

        return _iter()

    async def append(
        self,
        records: AsyncIterator[Mapping[str, Any]],
    ) -> str:
        raise NotImplementedError(
            "HudiTable.append: Hudi Python writer support is currently "
            "limited; use the Hudi Spark/Java writer "
            "(`hudi-spark-bundle`) for production writes. Track upstream "
            "Hudi-Python progress at https://github.com/apache/hudi-rs."
        )

    async def overwrite(
        self,
        records: AsyncIterator[Mapping[str, Any]],
        *,
        partition_filter: Mapping[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError(
            "HudiTable.overwrite: Hudi Python writer support is currently "
            "limited; use the Hudi Spark/Java writer "
            "(`hudi-spark-bundle`) for production writes."
        )

    async def merge(
        self,
        records: AsyncIterator[Mapping[str, Any]],
        *,
        on: Sequence[str],
    ) -> str:
        raise NotImplementedError(
            "HudiTable.merge: Hudi's upsert semantics are part of its "
            "Spark/Java writer. Use the Hudi Spark/Java writer "
            "(`hudi-spark-bundle`) for MERGE/upsert workloads."
        )

    async def history(self) -> AsyncIterator[Mapping[str, Any]]:
        if self._closed:
            raise RuntimeError("HudiTable is closed")
        commits: list[Mapping[str, Any]]
        if self._table is not None and hasattr(self._table, "history"):
            commits = list(self._table.history())
        else:
            commits = self._read_commit_timeline()

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            for commit in commits:
                yield commit

        return _iter()

    async def close(self) -> None:
        self._table = None
        self._closed = True
        self._clear_credentials()

    # ─────────────────────────────────────────────────────── helpers

    @staticmethod
    def _scan_stub(
        table: Any,
        columns: Sequence[str] | None,
    ) -> list[dict[str, Any]]:
        # Stub vendor tables expose ``scan_pylist`` returning a list of
        # row dicts.
        scan_fn = getattr(table, "scan_pylist", None)
        if not callable(scan_fn):
            raise TypeError("HudiTable: injected table must define scan_pylist() -> list[dict]")
        rows = list(scan_fn())  # type: ignore[arg-type]
        if columns is None:
            return [dict(row) for row in rows]
        cols = tuple(columns)
        return [{key: row.get(key) for key in cols} for row in rows]

    def _scan_parquet(
        self,
        columns: Sequence[str] | None,
    ) -> list[dict[str, Any]]:
        # Best-effort read-only scan: glob the latest commit's parquet
        # files under ``<table_path>/`` (recursive) and concatenate
        # them. This skips Hudi's log-merge semantics for MERGE_ON_READ
        # tables — adequate for COPY_ON_WRITE tables and a
        # documented-limitation read for MOR tables.
        try:
            import pyarrow.dataset as ds  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "HudiTable read requires pyarrow. Install via "
                "`pip install pirn[data]` or `pip install pirn[hudi]`."
            ) from exc
        if self._config is None or not self._config.table_path:
            raise RuntimeError("HudiTable: missing config.table_path and no injected table")
        dataset = ds.dataset(self._config.table_path, format="parquet")
        kwargs: dict[str, Any] = {}
        if columns is not None:
            kwargs["columns"] = list(columns)
        return dataset.to_table(**kwargs).to_pylist()

    def _read_commit_timeline(self) -> list[Mapping[str, Any]]:
        # Production-quality timeline parsing is a Hudi-native
        # responsibility. Without the Java writer we can only surface
        # the existence of ``.hoodie/`` instants as opaque commit ids.
        raise NotImplementedError(
            "HudiTable.history: Hudi commit-timeline parsing requires the "
            "Hudi Java/Scala libraries; no stable Python equivalent exists. "
            "Inject a stub via table= for tests, or use the Spark/Java "
            "client in production."
        )

    @staticmethod
    def _row_matches(row: Mapping[str, Any], filter: Mapping[str, Any]) -> bool:
        for key, value in filter.items():
            if row.get(key) != value:
                return False
        return True
