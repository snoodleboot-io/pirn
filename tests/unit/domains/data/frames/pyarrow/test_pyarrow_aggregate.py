"""Tests for :class:`PyarrowAggregate`."""

from __future__ import annotations

import pyarrow as pa
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pyarrow.pyarrow_aggregate import PyarrowAggregate
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
from pirn.tapestry import Tapestry


@knot
async def emit_orders() -> PyarrowDataBatch:
    return PyarrowDataBatch(
        table=pa.table(
            {
                "region":   ["EU", "EU", "EU", "US"],
                "customer": ["alice", "bob", "alice", "carol"],
                "amount":   [10.0, 25.0, 5.0, 100.0],
            }
        )
    )


@knot
async def emit_empty() -> PyarrowDataBatch:
    return PyarrowDataBatch(table=pa.table({"a": pa.array([], type=pa.int64())}))


@pytest.mark.asyncio
class TestPyarrowAggregate:
    async def test_sum_per_region(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            PyarrowAggregate(
                batch=batch,
                by=("region",),
                aggs={"total": ("amount", "sum")},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["agg"]
        # Output column order is the by-columns followed by the agg outputs.
        assert out.table.column_names == ["region", "total"]
        rows = out.table.to_pylist()
        totals = {row["region"]: row["total"] for row in rows}
        assert totals["EU"] == 40.0
        assert totals["US"] == 100.0

    async def test_multiple_aggregations_preserve_output_order(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            PyarrowAggregate(
                batch=batch,
                by=("region",),
                aggs={
                    "total":       ("amount", "sum"),
                    "n_orders":    ("amount", "count"),
                    "n_customers": ("customer", "count_distinct"),
                },
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["agg"]
        assert out.table.column_names == [
            "region",
            "total",
            "n_orders",
            "n_customers",
        ]
        rows = {row["region"]: row for row in out.table.to_pylist()}
        assert rows["EU"]["total"] == 40.0
        assert rows["EU"]["n_orders"] == 3
        assert rows["EU"]["n_customers"] == 2
        assert rows["US"]["n_customers"] == 1


class TestConstruction:
    def test_rejects_string_by(self) -> None:
        with Tapestry():
            batch = emit_empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="sequence"):
                PyarrowAggregate(
                    batch=batch,
                    by="a",  # type: ignore[arg-type]
                    aggs={"total": ("a", "sum")},
                    _config=KnotConfig(id="agg"),
                )

    def test_rejects_empty_by(self) -> None:
        with Tapestry():
            batch = emit_empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="non-empty"):
                PyarrowAggregate(
                    batch=batch,
                    by=(),
                    aggs={"total": ("a", "sum")},
                    _config=KnotConfig(id="agg"),
                )

    def test_rejects_unsafe_by_column(self) -> None:
        with Tapestry():
            batch = emit_empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="plain identifier"):
                PyarrowAggregate(
                    batch=batch,
                    by=("region; DROP TABLE t",),
                    aggs={"total": ("a", "sum")},
                    _config=KnotConfig(id="agg"),
                )

    def test_rejects_non_mapping_aggs(self) -> None:
        with Tapestry():
            batch = emit_empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="Mapping"):
                PyarrowAggregate(
                    batch=batch,
                    by=("a",),
                    aggs=[("total", ("a", "sum"))],  # type: ignore[arg-type]
                    _config=KnotConfig(id="agg"),
                )

    def test_rejects_empty_aggs(self) -> None:
        with Tapestry():
            batch = emit_empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="non-empty"):
                PyarrowAggregate(
                    batch=batch,
                    by=("a",),
                    aggs={},
                    _config=KnotConfig(id="agg"),
                )

    def test_rejects_unsafe_output_name(self) -> None:
        with Tapestry():
            batch = emit_empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="plain identifier"):
                PyarrowAggregate(
                    batch=batch,
                    by=("a",),
                    aggs={"bad name!": ("a", "sum")},
                    _config=KnotConfig(id="agg"),
                )

    def test_rejects_unknown_function(self) -> None:
        with Tapestry():
            batch = emit_empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="not supported"):
                PyarrowAggregate(
                    batch=batch,
                    by=("a",),
                    aggs={"total": ("a", "median")},
                    _config=KnotConfig(id="agg"),
                )

    def test_accepts_valid_inputs(self) -> None:
        with Tapestry():
            batch = emit_empty(_config=KnotConfig(id="empty"))
            knot_instance = PyarrowAggregate(
                batch=batch,
                by=("a",),
                aggs={"total": ("a", "sum")},
                _config=KnotConfig(id="agg"),
            )
        assert knot_instance.by == ("a",)
        assert knot_instance.aggs == {"total": ("a", "sum")}
