"""ATDD acceptance test: Tier-3 Ibis push-down end-to-end.

This is the gating test for Tier 3. It proves that:

1. ``IbisSource``, ``IbisFilter``, ``IbisGroupByAggregate``, and
   ``IbisJoin`` all produce *deferred* expressions that pirn can flow
   between knots.
2. NONE of those intermediate knots execute against the backend — only
   :class:`IbisToTable` triggers compilation and execution.
3. The whole pipeline is materialised as one compiled SQL query against
   the backend, not as a sequence of round-trips.
4. The sink writes results back into the warehouse and returns a small
   :class:`IbisExecutionReceipt` for lineage — no rows are materialised
   into the Python process unless the sink is the no-target form.

If this test fails, push-down is broken at some layer.
"""

from __future__ import annotations

import ibis
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.ibis.ibis_execution_receipt import IbisExecutionReceipt
from pirn.domains.data.lazy.ibis.ibis_filter import IbisFilter
from pirn.domains.data.lazy.ibis.ibis_group_by_aggregate import IbisGroupByAggregate
from pirn.domains.data.lazy.ibis.ibis_join import IbisJoin
from pirn.domains.data.lazy.ibis.ibis_source import IbisSource
from pirn.domains.data.lazy.ibis.ibis_to_table import IbisToTable
from pirn.tapestry import Tapestry


class _ExecutionRecorder:
    """Wraps an Ibis backend connection and counts execute() calls."""

    def __init__(self, connection):
        self._connection = connection
        self.execute_calls: list[str] = []

    def __getattr__(self, item):
        return getattr(self._connection, item)

    def execute(self, expression, *args, **kwargs):
        compiled = str(self._connection.compile(expression))
        self.execute_calls.append(compiled)
        return self._connection.execute(expression, *args, **kwargs)


@pytest.fixture
def duckdb_recorded():
    base = ibis.duckdb.connect()
    base.create_table(
        "users",
        {"user_id": [1, 2, 3, 4], "region": ["EU", "EU", "US", "US"]},
    )
    base.create_table(
        "orders",
        {
            "user_id": [1, 1, 2, 3, 3, 4],
            "amount":  [10.0, 25.0, 5.0, 100.0, 50.0, 1.0],
            "active":  [True, True, False, True, True, False],
        },
    )
    return _ExecutionRecorder(base)


@pytest.mark.asyncio
async def test_push_down_pipeline_executes_once(duckdb_recorded) -> None:
    with Tapestry() as t:
        users = IbisSource(
            connection=duckdb_recorded, table="users",
            backend_name="duckdb",
            _config=KnotConfig(id="users", validate_io=False),
        )
        orders = IbisSource(
            connection=duckdb_recorded, table="orders",
            backend_name="duckdb",
            _config=KnotConfig(id="orders", validate_io=False),
        )
        active_orders = IbisFilter(
            batch=orders,
            predicate=lambda table: table.active,
            _config=KnotConfig(id="active"),
        )
        joined = IbisJoin(
            left=users, right=active_orders,
            predicates=("user_id",),
            how="inner",
            _config=KnotConfig(id="joined"),
        )
        totals = IbisGroupByAggregate(
            batch=joined,
            by=("region",),
            aggregations=lambda table: table.amount.sum().name("total"),
            _config=KnotConfig(id="totals"),
        )
        IbisToTable(
            batch=totals,
            connection=duckdb_recorded,
            target_table="region_totals",
            _config=KnotConfig(id="materialise", validate_io=False),
        )

    result = await t.run(RunRequest())

    # Every knot in the pipeline reports `ok` in lineage.
    outcomes = {rec.knot_id: rec.outcome for rec in result.lineage}
    assert all(
        outcomes[k] == "ok"
        for k in ("users", "orders", "active", "joined", "totals", "materialise")
    ), outcomes

    receipt: IbisExecutionReceipt = result.outputs["materialise"]
    assert receipt.target_table == "region_totals"
    assert receipt.row_count == 2  # 2 regions
    sql = receipt.compiled_sql.lower()
    # All push-down landmarks should appear in the single compiled query.
    assert "where" in sql        # filter
    assert "group by" in sql      # aggregate
    assert "join" in sql          # join
    assert "sum" in sql           # aggregation

    # Confirm only the sink triggered .execute() against the backend.
    # Source / filter / aggregate / join were *deferred* — no execute.
    assert duckdb_recorded.execute_calls, "Expected at least one execute call"
    # The sink does compile + execute (twice when target_table is set:
    # once to materialise, once for the COUNT). We assert no more than that.
    assert len(duckdb_recorded.execute_calls) <= 2, duckdb_recorded.execute_calls

    # And the destination table holds the per-region totals.
    persisted = duckdb_recorded.execute(
        duckdb_recorded.table("region_totals")
    ).set_index("region")
    # EU active orders: 10 + 25 = 35 (user 1's two orders); US active: 100+50 = 150
    assert persisted.loc["EU", "total"] == 35.0
    assert persisted.loc["US", "total"] == 150.0
