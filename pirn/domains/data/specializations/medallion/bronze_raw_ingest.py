"""``BronzeRawIngest`` — preserve-as-received ingestion to a "bronze"
landing zone.

The medallion architecture (bronze → silver → gold) starts with bronze:
the unmodified record from the source plus minimal envelope metadata
(``ingested_at``, ``source_uri``). No type coercion, no normalisation,
no dedup — anything that mutates the raw row defeats bronze's job as the
last line of audit / replay defence.

Composition:
1. :class:`DatabaseQuerySource` reads from the source pool.
2. :class:`StampBronzeMetadataKnot` decorates each row with
   ``_ingested_at`` and ``_source_uri``.
3. :class:`DatabaseExecuteSink` appends to the target table.

The target table must declare ``_ingested_at`` and ``_source_uri``
columns; the bundled stamp knot supplies those values.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn.domains.connectors.knots.database_query_source import DatabaseQuerySource
from pirn.domains.data.specializations.medallion.stamp_bronze_metadata_knot import (
    StampBronzeMetadataKnot,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class BronzeRawIngest(SubTapestry):
    """Ingest source rows into a bronze table with envelope metadata."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        source_columns: Sequence[str],
        source_uri: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "BronzeRawIngest: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "BronzeRawIngest: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
            ("source_uri", source_uri),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"BronzeRawIngest: {label} must be a non-empty string"
                )
        column_tuple = tuple(source_columns)
        if not column_tuple:
            raise ValueError("BronzeRawIngest: source_columns must be non-empty")
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._source_columns = column_tuple
        self._source_uri = source_uri
        super().__init__(_config=_config, **kwargs)

    @property
    def insert_query(self) -> str:
        all_cols = list(self._source_columns) + ["_ingested_at", "_source_uri"]
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return (
            f"INSERT INTO {self._target_table} ({column_list}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> RunResult:
        with Tapestry() as inner:
            extracted = DatabaseQuerySource(
                pool=self._source_pool,
                query=self._source_query,
                _config=KnotConfig(id="extract"),
            )
            stamped = StampBronzeMetadataKnot(
                rows=extracted,
                source_uri=self._source_uri,
                _config=KnotConfig(id="stamp"),
            )
            DatabaseExecuteSink(
                pool=self._target_pool,
                query=self.insert_query,
                rows=stamped,
                _config=KnotConfig(id="load"),
            )
        return await self._run_inner(inner)
