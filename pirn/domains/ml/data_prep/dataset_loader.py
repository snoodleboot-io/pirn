"""``DatasetLoader`` — loads an :class:`MLDataset` from a database query
or a parquet file.

The knot does not embed dataset rows in its output. It produces a
metadata reference (an :class:`MLDataset`) that downstream knots resolve
when they need to materialise the data. ``row_count`` is computed from
the source so the reference carries enough provenance for lineage.

Algorithm:
    1. Receive ``name``, ``feature_names``, ``target_name``, ``pool``,
       ``query``, and ``parquet_path`` via process().
    2. Validate that exactly one of (pool + query) or parquet_path is provided.
    3. Count rows from the selected source.
    4. Return an MLDataset reference with provenance metadata.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.ml.types.ml_dataset import MLDataset


class DatasetLoader(Knot):
    """Materialise an :class:`MLDataset` reference from a SQL query or parquet."""

    def __init__(
        self,
        *,
        name: Knot | str,
        feature_names: Knot | Sequence[str],
        target_name: Knot | str | None = None,
        pool: Knot | DatabaseConnectionPool | None = None,
        query: Knot | str | None = None,
        parquet_path: Knot | str | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name=name,
            feature_names=feature_names,
            target_name=target_name,
            pool=pool,
            query=query,
            parquet_path=parquet_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        name: str = "",
        feature_names: Sequence[str] = (),
        target_name: str | None = None,
        pool: DatabaseConnectionPool | None = None,
        query: str | None = None,
        parquet_path: str | None = None,
        **_: Any,
    ) -> MLDataset:
        """Count rows from the SQL query or parquet path and return an MLDataset reference.

        Args:
            name: Non-empty dataset name.
            feature_names: Non-empty sequence of feature column names.
            target_name: Optional target column name.
            pool: DatabaseConnectionPool for SQL loading (mutually exclusive with parquet_path).
            query: Non-empty SQL query string (required when pool is provided).
            parquet_path: Non-empty path to a parquet file (mutually exclusive with pool/query).

        Returns:
            MLDataset reference with row_count derived from the SQL query or parquet file.

        Raises:
            ValueError: If inputs fail validation or source exclusivity is violated.
            TypeError: If pool is not a DatabaseConnectionPool.
        """
        if not isinstance(name, str) or not name:
            raise ValueError("DatasetLoader: name must be a non-empty string")
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError("DatasetLoader: feature_names must be non-empty")
        for feature in feature_tuple:
            if not isinstance(feature, str) or not feature:
                raise ValueError(
                    "DatasetLoader: every feature name must be a non-empty string"
                )
        has_pool_query = pool is not None and query is not None
        has_parquet = parquet_path is not None
        if has_pool_query == has_parquet:
            raise ValueError(
                "DatasetLoader: provide exactly one of (pool + query) "
                "or parquet_path"
            )
        if pool is not None and not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "DatasetLoader: pool must be a DatabaseConnectionPool"
            )
        if query is not None and (not isinstance(query, str) or not query):
            raise ValueError(
                "DatasetLoader: query must be a non-empty string"
            )
        if parquet_path is not None and (
            not isinstance(parquet_path, str) or not parquet_path
        ):
            raise ValueError(
                "DatasetLoader: parquet_path must be a non-empty string"
            )
        if has_pool_query:
            row_count = await self._count_pool_rows(pool, query)
            source_uri = f"db://{type(pool).__name__}"
        else:
            row_count = await self._count_parquet_rows(parquet_path)
            source_uri = f"file://{parquet_path}"
        return MLDataset(
            name=name,
            feature_names=feature_tuple,
            target_name=target_name,
            row_count=row_count,
            source_uri=source_uri,
            fetched_at=datetime.now(UTC),
        )

    async def _count_pool_rows(self, pool: DatabaseConnectionPool, query: str) -> int:
        fetch_all = getattr(pool, "fetch_all", None)
        if fetch_all is None:
            raise TypeError(
                "DatasetLoader: pool does not support fetch_all()"
            )
        rows = await fetch_all(query)
        return len(rows)

    async def _count_parquet_rows(self, parquet_path: str) -> int:
        # Defer the import; the parquet path is optional for callers
        # that only ever use the SQL route.
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError(
                "DatasetLoader: parquet_path requires pyarrow; install "
                "the data extra"
            ) from exc
        table = pq.read_table(parquet_path)
        return int(table.num_rows)
