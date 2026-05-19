`pirn.domains.data.frames` provides Tier 2 in-memory frame knots for Polars, pandas, PyArrow, and DuckDB — it does not push work to external engines; for out-of-core or distributed execution see `pirn.domains.data.lazy` (Tier 3).

---

## Mental model

Tier 2 knots materialize data into an in-memory frame, transform it, and emit a `DataBatch`. Each engine (Polars, pandas, PyArrow, DataFusion) has an identical set of operation knots (filter, join, aggregate, cast, rename, deduplicate). Pick the engine by throughput need and existing dependencies — Polars is the default for new code (fastest single-node), pandas for compatibility with ecosystem libraries.

Bridge knots convert between engine frame types so you can mix engines within one tapestry.

---

## Source map

```
pirn/domains/data/frames/
│
│  ── Polars (preferred Tier 2 engine) ──
├── polars/
│   ├── polars_data_batch.py    PolarsDataBatch    — DataBatch backed by a polars.DataFrame
│   ├── polars_filter.py        PolarsFilter       — filter rows by expression
│   ├── polars_join.py          PolarsJoin         — join two DataBatches
│   ├── polars_aggregate.py     PolarsAggregate    — group-by + aggregate
│   ├── polars_pivot.py         PolarsPrivot       — pivot rows to columns
│   ├── polars_cast.py          PolarsCast         — cast column types
│   ├── polars_rename.py        PolarsRename       — rename columns
│   ├── polars_deduplicate.py   PolarsDedup        — deduplicate rows
│   └── bridges/               (engine bridge knots — internal)
│
│  ── pandas ──
├── pandas/
│   ├── pandas_data_batch.py    PandasDataBatch    — DataBatch backed by pd.DataFrame
│   ├── pandas_filter.py        PandasFilter       — filter rows
│   ├── pandas_join.py          PandasJoin         — join two DataBatches
│   ├── pandas_aggregate.py     PandasAggregate    — group-by + aggregate
│   ├── pandas_cast.py          PandasCast         — cast column types
│   ├── pandas_rename.py        PandasRename       — rename columns
│   ├── pandas_deduplicate.py   PandasDedup        — deduplicate rows
│   └── bridges/               (engine bridge knots — internal)
│
│  ── PyArrow ──
├── pyarrow/
│   └── (filter, join, aggregate, cast, rename — same pattern)
│
│  ── DataFusion ──
└── datafusion/
    └── (filter, join, aggregate, cast — same pattern; SQL-based)
```

---

## Canonical pattern

### Polars filter → aggregate

```python
from pirn.domains.data.frames.polars.polars_filter import PolarsFilter
from pirn.domains.data.frames.polars.polars_aggregate import PolarsAggregate
from pirn import Tapestry, KnotConfig, RunRequest

with Tapestry() as t:
    rows     = SourceKnot(_config=KnotConfig(id="source"))
    active   = PolarsFilter(
        data=rows,
        predicate='status == "active"',
        _config=KnotConfig(id="filter"),
    )
    by_region = PolarsAggregate(
        data=active,
        group_by=["region"],
        aggregations={"revenue": "sum", "count": "len"},
        _config=KnotConfig(id="agg"),
    )
```

### Join two sources

```python
from pirn.domains.data.frames.polars.polars_join import PolarsJoin

with Tapestry() as t:
    orders    = OrdersSource(_config=KnotConfig(id="orders"))
    customers = CustomerSource(_config=KnotConfig(id="customers"))
    joined    = PolarsJoin(
        left=orders, right=customers,
        on="customer_id", how="left",
        _config=KnotConfig(id="join"),
    )
```

---

## Anti-patterns

**Using pandas when Polars is available** — Polars is 5–50× faster than pandas for most frame operations. Use pandas only when a downstream library (scikit-learn, statsmodels, etc.) requires a `pd.DataFrame`.

**Mixing frame engines without bridge knots** — passing a `PolarsDataBatch` directly to a `PandasFilter` will fail at runtime. Use the bridge knots in `bridges/` to convert between engines.

---

## Constraints and gotchas

- **Polars predicate syntax uses Polars expression strings**, not pandas boolean indexing. `'col > 5 and status == "active"'` must be valid Polars string expressions.
- **`DataFusion` knots use SQL predicates** — pass a `WHERE` clause string without the `WHERE` keyword.
- **Each engine requires its own extra:** `pirn[polars]`, `pirn[pandas]`, `pirn[pyarrow]`, `pirn[datafusion]`. Polars and PyArrow are included in `pirn[data]`.
- **Frame knots are in-memory.** For datasets that do not fit in RAM, use Tier 3 lazy knots (`pirn.domains.data.lazy`) with Dask, Ibis, or Spark.

---

## Quick reference

| Operation | Polars | pandas |
|-----------|--------|--------|
| Filter rows | `PolarsFilter` | `PandasFilter` |
| Join | `PolarsJoin` | `PandasJoin` |
| Group-by aggregate | `PolarsAggregate` | `PandasAggregate` |
| Cast types | `PolarsCast` | `PandasCast` |
| Rename columns | `PolarsRename` | `PandasRename` |
| Deduplicate | `PolarsDedup` | `PandasDedup` |

---

*See also: [data AGENTIC_USE.md](../AGENTIC_USE.md)*
