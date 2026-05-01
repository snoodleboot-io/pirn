"""``SilverCleanTransform`` — cleanse + dedup + validate a bronze batch
into a silver table.

Composition (Tier-1 dict-based — small batches; for medium/large data,
the same shape works at Tier-2 by swapping in PolarsFilter / PolarsCast
/ PolarsDeduplicate):

1. :class:`DatabaseQuerySource` reads from the bronze source.
2. The bronze rows are normalised into a Tier-1 :class:`DataBatch`.
3. :class:`Cast` coerces column types per the caller's schema.
4. :class:`Filter` drops rows that fail caller-supplied validity rules.
5. :class:`Deduplicate` enforces the silver primary key.
6. The cleaned rows are written via :class:`DatabaseExecuteSink`.

The pipeline produces a *silver* table — typed, deduped, business-rule-
validated, but not yet aggregated. Aggregation is :class:`GoldAggregation`.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn.domains.connectors.knots.database_query_source import DatabaseQuerySource
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.specializations.medallion.tuples_to_data_batch_knot import (
    TuplesToDataBatchKnot,
)
from pirn.domains.data.specializations.medallion.data_batch_to_tuples_knot import (
    DataBatchToTuplesKnot,
)
from pirn.domains.data.transforms.cast import Cast
from pirn.domains.data.transforms.deduplicate import Deduplicate
from pirn.domains.data.transforms.filter import Filter
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class SilverCleanTransform(SubTapestry):
    """Bronze → Silver: cast types, filter invalid rows, dedup on PK."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        column_names: Sequence[str],
        casts: Mapping[str, type],
        filter_predicate: Callable[[Mapping[str, Any]], bool],
        primary_keys: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "SilverCleanTransform: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "SilverCleanTransform: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"SilverCleanTransform: {label} must be a non-empty string"
                )
        column_tuple = tuple(column_names)
        if not column_tuple:
            raise ValueError("SilverCleanTransform: column_names must be non-empty")
        primary_key_tuple = tuple(primary_keys)
        if not primary_key_tuple:
            raise ValueError("SilverCleanTransform: primary_keys must be non-empty")
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._column_names = column_tuple
        self._casts = dict(casts)
        self._filter_predicate = filter_predicate
        self._primary_keys = primary_key_tuple
        self._insert_query = self._build_insert_query()
        super().__init__(_config=_config, **kwargs)

    def _build_insert_query(self) -> str:
        column_list = ", ".join(self._column_names)
        placeholders = ", ".join(["?"] * len(self._column_names))
        return (
            f"INSERT INTO {self._target_table} ({column_list}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        with Tapestry() as inner:
            extracted = DatabaseQuerySource(
                pool=self._source_pool,
                query=self._source_query,
                _config=KnotConfig(id="extract"),
            )
            as_batch = TuplesToDataBatchKnot(
                rows=extracted,
                column_names=self._column_names,
                _config=KnotConfig(id="as_batch"),
            )
            casted = Cast(
                batch=as_batch,
                casts=self._casts,
                _config=KnotConfig(id="cast"),
            )
            valid = Filter(
                batch=casted,
                predicate=self._filter_predicate,
                _config=KnotConfig(id="filter"),
            )
            deduped = Deduplicate(
                batch=valid,
                keys=self._primary_keys,
                _config=KnotConfig(id="dedup"),
            )
            tuples = DataBatchToTuplesKnot(
                batch=deduped,
                column_names=self._column_names,
                _config=KnotConfig(id="to_tuples"),
            )
            DatabaseExecuteSink(
                pool=self._target_pool,
                query=self._insert_query,
                rows=tuples,
                _config=KnotConfig(id="load"),
            )
        inner_result = await self._run_inner(inner)
        # Return a primitive summary so pirn's content-addressing hash
        # does not have to walk a RunResult whose outputs contain
        # DataBatch (with type-bearing schemas).
        return {
            "succeeded": inner_result.succeeded,
            "target_table": self._target_table,
        }
