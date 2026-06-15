`pirn_data.lazy` provides Tier 3 push-down and distributed frame knots for Ibis, Dask, Ray, and Spark — it does not materialize data in-process; execution is deferred to the connected engine or cluster.

---

## Mental model

Tier 3 knots build a logical query plan and push it to an external engine for execution. The engine is responsible for parallelization, memory management, and optimization. The knot emits a `DataBatch` only after the engine returns results (or a lazy reference that materializes on demand).

Ibis is the preferred Tier 3 engine for SQL-backed stores (any database with an Ibis backend). Dask is preferred for Python-native out-of-core work. Spark handles large Hadoop/HDFS-backed workloads. Ray integrates with the `RayDispatcher`.

---

## Source map

```
pirn_data/lazy/
│
│  ── Ibis (preferred Tier 3 for SQL-backed engines) ──
├── ibis/
│   ├── ibis_source.py              IbisSource              — read a table from an Ibis backend as lazy relation
│   ├── ibis_table.py               IbisTable               — wrap an ibis Table expression as a DataBatch
│   ├── ibis_filter.py              IbisFilter              — push-down filter (WHERE)
│   ├── ibis_join.py                IbisJoin                — push-down join
│   ├── ibis_group_by_aggregate.py  IbisGroupByAggregate    — push-down group-by aggregate
│   ├── ibis_window.py              IbisWindow              — push-down window function
│   ├── ibis_to_table.py            IbisToTable             — execute Ibis expression; return DataBatch
│   ├── ibis_connection.py          IbisConnection          — Ibis backend connection (wraps DB pool)
│   ├── ibis_connection_knot.py     IbisConnectionKnot      — expose IbisConnection as a knot output
│   └── ibis_execution_receipt.py   IbisExecutionReceipt    — value type: Ibis execute result metadata
│
│  ── Dask ──
├── dask/
│   └── (filter, join, aggregate, repartition — same operation set as frames tier)
│
│  ── Ray ──
├── ray/
│   └── (map, filter, group-by — Dataset-based operations)
│
│  ── Spark ──
└── spark/
    └── (filter, join, aggregate, window — DataFrame API)
```

---

## Canonical pattern

### Ibis — push-down aggregate on a Postgres table

```python
from pirn_data.lazy.ibis.ibis_connection import IbisConnection
from pirn_data.lazy.ibis.ibis_source import IbisSource
from pirn_data.lazy.ibis.ibis_group_by_aggregate import IbisGroupByAggregate
from pirn_data.lazy.ibis.ibis_to_table import IbisToTable
from pirn import Tapestry, KnotConfig, RunRequest

conn = IbisConnection(pool=my_postgres_pool)

with Tapestry() as t:
    table   = IbisSource(connection=conn, table_name="events",
                          _config=KnotConfig(id="src"))
    agg     = IbisGroupByAggregate(
        table=table,
        group_by=["region"],
        aggregations={"revenue": "sum"},
        _config=KnotConfig(id="agg"),
    )
    result  = IbisToTable(relation=agg, _config=KnotConfig(id="execute"))
```

---

## Anti-patterns

**Using Ibis knots without calling `IbisToTable`** — Ibis builds a lazy expression graph. Without `IbisToTable` at the end, nothing executes. The downstream knot will receive an `ibis.Table` expression, not a materialized `DataBatch`.

**Using Dask or Spark for small datasets** — these engines have per-partition overhead and cluster setup costs. For datasets that fit in RAM, Tier 2 Polars knots are faster and simpler.

---

## Constraints and gotchas

- **`IbisConnection` requires the Ibis backend for your database.** e.g. `pirn[ibis-postgres]`, `pirn[ibis-duckdb]`. Check `pyproject.toml` for available backends.
- **`IbisFilter`, `IbisJoin`, etc. do not execute immediately** — they build the expression. Only `IbisToTable` triggers execution.
- **Dask and Spark knots require a running cluster** or local scheduler. Pass the client/session to the knot constructor; pirn does not manage cluster lifecycle.
- **Ray knots are dataset-level** — they use `ray.data.Dataset`, not Ray actors. For actor-based work, use `RayDispatcher` at the tapestry level instead.

---

## Quick reference

| Engine | When to use | Entry point |
|--------|------------|------------|
| Ibis | SQL-backed store (Postgres, DuckDB, Snowflake, BigQuery) | `IbisSource` → ops → `IbisToTable` |
| Dask | Out-of-core Python, CSV/Parquet partitioned files | Dask filter/join/aggregate knots |
| Spark | HDFS, large-scale ETL, existing Spark cluster | Spark filter/join/aggregate knots |
| Ray | ML workloads, works with `RayDispatcher` | Ray map/filter/group-by knots |

---

*See also: [data AGENTIC_USE.md](../AGENTIC_USE.md)*
