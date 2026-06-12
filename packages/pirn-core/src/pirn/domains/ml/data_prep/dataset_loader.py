"""``DatasetLoader`` — load a :class:`DatasetPayload` from any configured source.

Tries all configured sources concurrently inside an inner tapestry.  Each
source is wrapped with :class:`Optional` so a missing or failing source
produces ``Skipped`` rather than an error.  An :class:`Aggregator` picks
whichever source succeeded; exactly one must produce a result.  A
:class:`_DatasetAssembler` knot converts the raw :class:`DataBatch` into
a typed :class:`DatasetPayload` as the terminal step of the inner graph.

Because ``Optional`` intercepts both construction failures (e.g. ``store=None``
rejected by ``FileSource``) and runtime failures (e.g. file not found), the
caller simply passes all possible source config and leaves the rest as
``None`` — the pipeline resolves which source is live at runtime with no
branching logic in this class.

Supported sources
-----------------
* **File** — any ``ObjectStore`` x ``FileFormat`` combination (local disk,
  S3, GCS, Azure Blob, …) via :class:`~pirn.domains.data.sources.file_source.FileSource`
* **Lakehouse** — Delta Lake, Iceberg, Hudi native scan API via
  :class:`~pirn.domains.data.lakehouse.lakehouse_table_source.LakehouseTableSource`
* **SQL** — any ``DatabaseConnectionPool`` (SQLite, DuckDB, Postgres, …) via
  :class:`~pirn.domains.data.sources.sql_source.SqlSource`

References
----------
pirn/domains/data/sources/file_source.py
pirn/domains/data/sources/sql_source.py
pirn/domains/data/lakehouse/lakehouse_table_source.py
pirn/core/optional.py
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import numpy as np

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.file_format import FileFormat
from pirn.connectors.object_store import ObjectStore
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.optional import Optional
from pirn.core.skipped import Skipped
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.lakehouse.lakehouse_table import LakehouseTable
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.dataset_payload import DatasetPayload
from pirn.domains.ml.types.ml_features import MLFeatures
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry


class _DatasetAssembler(Knot):
    """Convert a raw :class:`DataBatch` into a typed :class:`DatasetPayload`.

    Terminal knot of the :class:`DatasetLoader` inner tapestry.  Extracts
    the feature matrix ``X`` and optional target vector ``y`` from the batch
    rows using the declared column names.
    """

    async def process(
        self,
        batch: DataBatch,
        name: str,
        feature_names: Sequence[str],
        target_name: str | None = None,
        **_: Any,
    ) -> DatasetPayload:
        if not name:
            raise ValueError("DatasetLoader: name must be a non-empty string")
        if not feature_names:
            raise ValueError("DatasetLoader: feature_names must be non-empty")

        rows = batch.rows
        if not rows:
            feature_matrix = np.empty((0, len(feature_names)), dtype=float)
            target_vector: np.ndarray | None = np.empty(0, dtype=float) if target_name else None
        else:
            try:
                raw_features = [[row[col] for col in feature_names] for row in rows]
            except (KeyError, TypeError) as exc:
                raise ValueError(
                    f"DatasetLoader: could not extract features from batch: {exc}"
                ) from exc
            try:
                feature_matrix = np.array(raw_features, dtype=float)
            except (TypeError, ValueError):
                feature_matrix = np.array(raw_features, dtype=object)
            target_vector = None
            if target_name:
                try:
                    raw_targets = [row[target_name] for row in rows]
                except (KeyError, TypeError) as exc:
                    raise ValueError(
                        f"DatasetLoader: could not extract target '{target_name}': {exc}"
                    ) from exc
                try:
                    target_vector = np.array([float(v) for v in raw_targets], dtype=float)
                except (TypeError, ValueError):
                    target_vector = np.array(raw_targets, dtype=object)

        manifest = DatasetManifest(
            name=name,
            feature_names=tuple(feature_names),
            target_name=target_name,
            row_count=int(feature_matrix.shape[0]),
            source_uri=batch.source_uri,
            fetched_at=datetime.now(UTC),
        )
        return DatasetPayload(
            metadata=manifest,
            data=MLFeatures(feature_matrix=feature_matrix, target_vector=target_vector),
        )


class DatasetLoader(SubTapestry):
    """Load feature and target arrays into a :class:`DatasetPayload`.

    Constructs an inner tapestry with all three source knots wrapped in
    :class:`Optional`.  Whichever source is configured succeeds; the rest
    skip.  The :class:`Aggregator` surfaces the live result and
    :class:`_DatasetAssembler` converts it into a :class:`DatasetPayload`.

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
        if not feature_names:
            raise ValueError("DatasetLoader: feature_names must be non-empty")

        from pirn.domains.data.lakehouse.lakehouse_table_source import LakehouseTableSource
        from pirn.domains.data.sources.file_source import FileSource
        from pirn.domains.data.sources.sql_source import SqlSource

        # All three sources are constructed unconditionally and wrapped in
        # Optional.  Optional intercepts construction failures (e.g. FileSource
        # rejecting store=None) and runtime failures alike, converting both to
        # Ok(Skipped(...)).  The Aggregator then picks whichever source
        # produced a real DataBatch.
        file_src = Optional(
            FileSource,
            store=store,
            format=file_format,
            key=key,
            _config=KnotConfig(id="src-file"),
        )
        lake_src = Optional(
            LakehouseTableSource,
            table=table,
            _config=KnotConfig(id="src-lake"),
        )
        sql_src = Optional(
            SqlSource,
            pool=pool,
            query=query,
            _config=KnotConfig(id="src-sql"),
        )
        agg = Aggregator(
            combine=self._first_present,
            file=file_src,
            lake=lake_src,
            sql=sql_src,
            _config=KnotConfig(id="agg"),
        )
        return _DatasetAssembler(
            batch=agg,
            name=name,
            feature_names=feature_names,
            target_name=target_name,
            _config=KnotConfig(id="assembler"),
        )

    @staticmethod
    def _first_present(**results: Any) -> Any:
        """Return the first non-``Skipped`` value from the source results."""
        for v in results.values():
            if not isinstance(v, Skipped):
                return v
        raise RuntimeError(
            "DatasetLoader: no source produced data — "
            "provide store+file_format+key, table, or pool+query"
        )
