"""``DatasetLoader`` — load a :class:`DatasetPayload` from the one configured source.

The caller configures exactly one source group; the loader wires that source
directly into a :class:`DatasetAssembler` inside an inner tapestry. Source
failures (a missing file, a failing query, an unreachable lakehouse) fail the
run with the source's own exception — nothing is converted to ``Skipped`` and
no other source is consulted.

Algorithm:
    1. Receive the dataset shape (``name``, ``feature_names``, ``target_name``)
       and every source option via process().
    2. Validate ``feature_names`` is non-empty.
    3. Resolve the configured source group: file (``store`` + ``file_format``
       + ``key``), lakehouse (``table``), or SQL (``pool`` + ``query``). A
       partially configured group, no group, or more than one group raises
       ``ValueError``.
    4. Wire the matching source knot and feed its :class:`DataBatch` to
       :class:`DatasetAssembler`, which is the inner graph's terminal.

Supported sources
-----------------
* **File** — any ``ObjectStore`` x ``FileFormat`` combination (local disk,
  S3, GCS, Azure Blob, …) via :class:`~pirn_data.sources.file_source.FileSource`
* **Lakehouse** — Delta Lake, Iceberg, Hudi native scan API via
  :class:`~pirn_data.lakehouse.lakehouse_table_source.LakehouseTableSource`
* **SQL** — any ``DatabaseConnectionPool`` (SQLite, DuckDB, Postgres, …) via
  :class:`~pirn_data.sources.sql_source.SqlSource`

References:
    pirn_data/sources/file_source.py
    pirn_data/sources/sql_source.py
    pirn_data/lakehouse/lakehouse_table_source.py
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.file_format import FileFormat
from pirn.connectors.object_store import ObjectStore
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry
from pirn_data.lakehouse.lakehouse_table import LakehouseTable

from pirn_ml.data_prep.dataset_assembler import DatasetAssembler


class DatasetLoader(SubTapestry):
    """Load feature and target arrays into a :class:`DatasetPayload`.

    Wires exactly one configured source into :class:`DatasetAssembler`; a
    failing source fails the run with its own error.

    Parameters
    ----------
    name:
        Dataset name embedded in the manifest.
    feature_names:
        Column names to extract as the feature matrix ``X``.
    target_name:
        Column name to extract as the target vector ``y``.  Optional.
    store, file_format, key:
        File source config — all three required together.
    table:
        Lakehouse source config.
    pool, query:
        SQL source config — both required together.
    """

    def __init__(
        self,
        *,
        name: Knot | str,
        feature_names: Knot | Sequence[str],
        target_name: Knot | str | None = None,
        store: Knot | ObjectStore | None = None,
        file_format: Knot | FileFormat | None = None,
        key: Knot | str | None = None,
        table: Knot | LakehouseTable | None = None,
        pool: Knot | DatabaseConnectionPool | None = None,
        query: Knot | str | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name=name,
            feature_names=feature_names,
            target_name=target_name,
            store=store,
            file_format=file_format,
            key=key,
            table=table,
            pool=pool,
            query=query,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        name: str = "",
        feature_names: Sequence[str] = (),
        target_name: str | None = None,
        store: ObjectStore | None = None,
        file_format: FileFormat | None = None,
        key: str | None = None,
        table: LakehouseTable | None = None,
        pool: DatabaseConnectionPool | None = None,
        query: str | None = None,
        **_: Any,
    ) -> Any:
        """Wire the one configured source into a DatasetAssembler and return the terminal knot.

        Args:
            name: Dataset name embedded in the manifest.
            feature_names: Non-empty column names for the feature matrix.
            target_name: Optional target column name.
            store: File source object store (with ``file_format`` and ``key``).
            file_format: File source format (with ``store`` and ``key``).
            key: File source object key (with ``store`` and ``file_format``).
            table: Lakehouse source table.
            pool: SQL source connection pool (with ``query``).
            query: SQL source query (with ``pool``).

        Returns:
            The inner :class:`DatasetAssembler` knot producing a :class:`DatasetPayload`.

        Raises:
            ValueError: If ``feature_names`` is empty, a source group is only
                partially configured, or not exactly one source group is configured.
        """
        if not feature_names:
            raise ValueError("DatasetLoader: feature_names must be non-empty")

        from pirn_data.lakehouse.lakehouse_table_source import LakehouseTableSource
        from pirn_data.sources.file_source import FileSource
        from pirn_data.sources.sql_source import SqlSource

        file_options = (store, file_format, key)
        sql_options = (pool, query)
        file_configured = DatasetLoader._group_configured(
            "file", ("store", "file_format", "key"), file_options
        )
        sql_configured = DatasetLoader._group_configured("sql", ("pool", "query"), sql_options)
        lake_configured = table is not None
        configured = [
            label
            for label, is_set in (
                ("store+file_format+key", file_configured),
                ("table", lake_configured),
                ("pool+query", sql_configured),
            )
            if is_set
        ]
        if len(configured) != 1:
            raise ValueError(
                "DatasetLoader: configure exactly one source — store+file_format+key, "
                f"table, or pool+query; got {configured or 'none'}"
            )
        source: Knot
        if store is not None and file_format is not None and key is not None:
            source = FileSource(
                store=store, format=file_format, key=key, _config=KnotConfig(id="src-file")
            )
        elif table is not None:
            source = LakehouseTableSource(table=table, _config=KnotConfig(id="src-lake"))
        elif pool is not None and query is not None:
            source = SqlSource(pool=pool, query=query, _config=KnotConfig(id="src-sql"))
        else:  # unreachable: exactly one group was confirmed configured above
            raise ValueError("DatasetLoader: no source configured")
        return DatasetAssembler(
            batch=source,
            name=name,
            feature_names=feature_names,
            target_name=target_name,
            _config=KnotConfig(id="assembler"),
        )

    @staticmethod
    def _group_configured(group: str, names: tuple[str, ...], values: tuple[object, ...]) -> bool:
        """Whether a source group is fully configured; a partial group raises ``ValueError``."""
        provided = [
            option for option, value in zip(names, values, strict=True) if value is not None
        ]
        if not provided:
            return False
        if len(provided) != len(names):
            missing = [option for option in names if option not in provided]
            raise ValueError(
                f"DatasetLoader: {group} source is partially configured — "
                f"got {provided}, missing {missing}"
            )
        return True
