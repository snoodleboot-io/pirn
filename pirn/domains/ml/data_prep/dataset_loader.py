"""``DatasetLoader`` — loads an :class:`MLDataset` from a database query
or a parquet file.

The knot does not embed dataset rows in its output. It produces a
metadata reference (an :class:`MLDataset`) that downstream knots resolve
when they need to materialise the data. ``row_count`` is computed from
the source so the reference carries enough provenance for lineage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

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
        name: str,
        feature_names: Sequence[str],
        target_name: str | None = None,
        pool: DatabaseConnectionPool | None = None,
        query: str | None = None,
        parquet_path: str | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._name = name
        self._feature_names = feature_tuple
        self._target_name = target_name
        self._pool = pool
        self._query = query
        self._parquet_path = parquet_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> MLDataset:
        """Count rows from the SQL query or parquet path and return an MLDataset reference.

        Returns:
            MLDataset reference with row_count derived from the SQL query or parquet file.
        """
        if self._pool is not None and self._query is not None:
            row_count = await self._count_pool_rows()
            source_uri = f"db://{type(self._pool).__name__}"
        else:
            row_count = await self._count_parquet_rows()
            source_uri = f"file://{self._parquet_path}"
        return MLDataset(
            name=self._name,
            feature_names=self._feature_names,
            target_name=self._target_name,
            row_count=row_count,
            source_uri=source_uri,
            fetched_at=datetime.now(timezone.utc),
        )

    async def _count_pool_rows(self) -> int:
        fetch_all = getattr(self._pool, "fetch_all", None)
        if fetch_all is None:
            raise TypeError(
                "DatasetLoader: pool does not support fetch_all()"
            )
        rows = await fetch_all(self._query)
        return len(rows)

    async def _count_parquet_rows(self) -> int:
        # Defer the import; the parquet path is optional for callers
        # that only ever use the SQL route.
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError(
                "DatasetLoader: parquet_path requires pyarrow; install "
                "the data extra"
            ) from exc
        table = pq.read_table(self._parquet_path)
        return int(table.num_rows)
