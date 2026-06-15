"""``SilverCleanTransform`` — cleanse, validate, and deduplicate a bronze
batch into a silver table.

Tier-1 dict-based pipeline (small batches).  For medium/large data, the
same shape works at Tier-2 by swapping in PolarsFilter / PolarsCast /
PolarsDeduplicate in place of the dict-based transforms.

Algorithm:
    1. Receive all inputs in ``process()`` and validate.
    2. Fetch bronze rows from ``source_pool`` via ``source_query``.
    3. Convert row tuples to a :class:`DataBatch` keyed by ``column_names``.
    4. Apply type casts per ``casts`` mapping.
    5. Drop rows where ``filter_predicate`` returns falsy.
    6. Deduplicate on ``primary_keys`` (first-occurrence wins).
    7. Project each surviving row back to a positional tuple.
    8. Write via ``target_pool.execute_many``.
    9. Return a summary dict with ``succeeded``, ``target_table``,
       and ``rows_inserted``.

References:
    [1] pirn — DataBatch: pirn_data/data_batch.py
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.data_batch import DataBatch


class SilverCleanTransform(Knot):
    """Bronze → Silver: cast types, filter invalid rows, dedup on PK."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        column_names: Knot | Sequence[str],
        casts: Knot | Mapping[str, type],
        filter_predicate: Knot | Callable[[Mapping[str, Any]], bool],
        primary_keys: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            column_names=column_names,
            casts=casts,
            filter_predicate=filter_predicate,
            primary_keys=primary_keys,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _build_insert_query(target_table: str, column_names: tuple[str, ...]) -> str:
        column_list = ", ".join(column_names)
        placeholders = ", ".join(["?"] * len(column_names))
        return f"INSERT INTO {target_table} ({column_list}) VALUES ({placeholders})"

    @staticmethod
    def _cast_batch(batch: DataBatch, casts: dict[str, type]) -> DataBatch:
        def cast_row(row: Mapping[str, Any]) -> dict[str, Any]:
            out: dict[str, Any] = {}
            for key, value in row.items():
                if key in casts and value is not None:
                    target = casts[key]
                    out[key] = value if isinstance(value, target) else target(value)
                else:
                    out[key] = value
            return out

        return batch.with_rows(tuple(cast_row(r) for r in batch.rows))

    @staticmethod
    def _filter_batch(
        batch: DataBatch,
        predicate: Callable[[Mapping[str, Any]], bool],
    ) -> DataBatch:
        return batch.with_rows(tuple(row for row in batch.rows if predicate(row)))

    @staticmethod
    def _deduplicate_batch(batch: DataBatch, primary_keys: tuple[str, ...]) -> DataBatch:
        seen: set[tuple[Any, ...]] = set()
        kept = []
        for row in batch.rows:
            key = tuple(row.get(k) for k in primary_keys)
            if key not in seen:
                seen.add(key)
                kept.append(row)
        return batch.with_rows(tuple(kept))

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        column_names: Any,
        casts: Any,
        filter_predicate: Any,
        primary_keys: Any,
        **_: Any,
    ) -> dict[str, Any]:
        """Validate inputs, fetch, cast, filter, dedup, write to silver, return summary.

        Args:
            source_pool: Pool to read bronze rows from.
            source_query: SELECT query to run against the source.
            target_pool: Pool to write silver rows to.
            target_table: Name of the silver target table.
            column_names: Ordered column names for both source and target.
            casts: Mapping of column name to target Python type.
            filter_predicate: Callable that returns truthy for rows to keep.
            primary_keys: Column names that form the dedup key.

        Returns:
            A dict with ``succeeded``, ``target_table``, and ``rows_inserted``.

        Raises:
            TypeError: If either pool is not a ``DatabaseConnectionPool``.
            ValueError: If any string argument is empty, or sequence arguments are empty.
        """
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("SilverCleanTransform: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("SilverCleanTransform: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("SilverCleanTransform: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("SilverCleanTransform: target_table must be a non-empty string")
        column_tuple = tuple(column_names)
        if not column_tuple:
            raise ValueError("SilverCleanTransform: column_names must be non-empty")
        primary_key_tuple = tuple(primary_keys)
        if not primary_key_tuple:
            raise ValueError("SilverCleanTransform: primary_keys must be non-empty")
        casts_dict = dict(casts)
        # Fetch bronze rows and convert to DataBatch.
        raw_rows = await source_pool.fetch_all(source_query)
        batch = DataBatch(
            rows=tuple(dict(zip(column_tuple, tuple(r), strict=False)) for r in raw_rows)
        )
        # Apply transform chain.
        batch = SilverCleanTransform._cast_batch(batch, casts_dict)
        batch = SilverCleanTransform._filter_batch(batch, filter_predicate)
        batch = SilverCleanTransform._deduplicate_batch(batch, primary_key_tuple)
        # Project to positional tuples for INSERT.
        output_rows = [tuple(row.get(col) for col in column_tuple) for row in batch.rows]
        insert_query = SilverCleanTransform._build_insert_query(target_table, column_tuple)
        await target_pool.execute_many(insert_query, output_rows)
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": len(output_rows),
        }
