"""Tests for :class:`PyarrowAggregate`."""

from __future__ import annotations

import unittest

try:
    import pyarrow  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyarrow not installed") from _e

import pyarrow as pa

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pyarrow.pyarrow_aggregate import PyarrowAggregate
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
from pirn.tapestry import Tapestry


def _empty_batch() -> PyarrowDataBatch:
    return PyarrowDataBatch(table=pa.table({"a": pa.array([], type=pa.int64())}))


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


class TestPyarrowAggregate(unittest.IsolatedAsyncioTestCase):
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


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_by_from_upstream_knot(self) -> None:
        @knot
        async def emit_by() -> tuple:
            return ("region",)

        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            by_knot = emit_by(_config=KnotConfig(id="by"))
            PyarrowAggregate(
                batch=batch,
                by=by_knot,
                aggs={"total": ("amount", "sum")},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["agg"]
        rows = {row["region"]: row["total"] for row in out.table.to_pylist()}
        assert rows["EU"] == 40.0
        assert rows["US"] == 100.0


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PyarrowAggregate:
        with Tapestry():
            batch = emit_empty(_config=KnotConfig(id="empty"))
            return PyarrowAggregate(
                batch=batch, _config=KnotConfig(id="agg"), **kwargs
            )

    async def test_rejects_string_by(self) -> None:
        k = self._make_knot(by="a", aggs={"total": ("a", "sum")})
        with self.assertRaisesRegex(TypeError, "sequence"):
            await k.process(
                batch=_empty_batch(), by="a", aggs={"total": ("a", "sum")}
            )

    async def test_rejects_empty_by(self) -> None:
        k = self._make_knot(by=(), aggs={"total": ("a", "sum")})
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_empty_batch(), by=(), aggs={"total": ("a", "sum")}
            )

    async def test_rejects_unsafe_by_column(self) -> None:
        k = self._make_knot(
            by=("region; DROP TABLE t",), aggs={"total": ("a", "sum")}
        )
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await k.process(
                batch=_empty_batch(),
                by=("region; DROP TABLE t",),
                aggs={"total": ("a", "sum")},
            )

    async def test_rejects_non_mapping_aggs(self) -> None:
        k = self._make_knot(by=("a",), aggs=[("total", ("a", "sum"))])
        with self.assertRaisesRegex(TypeError, "Mapping"):
            await k.process(
                batch=_empty_batch(),
                by=("a",),
                aggs=[("total", ("a", "sum"))],  # type: ignore[arg-type]
            )

    async def test_rejects_empty_aggs(self) -> None:
        k = self._make_knot(by=("a",), aggs={})
        with self.assertRaisesRegex(TypeError, "Mapping"):
            await k.process(batch=_empty_batch(), by=("a",), aggs={})

    async def test_rejects_unsafe_output_name(self) -> None:
        k = self._make_knot(by=("a",), aggs={"bad name!": ("a", "sum")})
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await k.process(
                batch=_empty_batch(),
                by=("a",),
                aggs={"bad name!": ("a", "sum")},
            )

    async def test_rejects_unknown_function(self) -> None:
        k = self._make_knot(by=("a",), aggs={"total": ("a", "median")})
        with self.assertRaisesRegex(ValueError, "not supported"):
            await k.process(
                batch=_empty_batch(),
                by=("a",),
                aggs={"total": ("a", "median")},
            )
