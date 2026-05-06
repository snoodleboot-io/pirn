# Knot Design Rules Audit Report

**Scan Date:** 2026-05-05  
**Method:** Full file reads per file, all rules verified by agents, one agent per thematic group

## Legend

| Column | Rule | Details |
|--------|------|---------|
| R1 | `__init__` body is ONLY `super().__init__(...)` | No validation, assignments, or logic |
| R2 | Every `__init__` param (except `_config`, `**kwargs`) appears by same name in `process()` | Ensures direct testability |
| R3 | No `raise` statements in `__init__` | All validation deferred to `process()` |
| R4 | No `self._x` assignments storing inputs | Inputs arrive fresh in `process()` |
| R5 | No `@property` exposing stored inputs or derived strings | Computed values via private helpers only |
| R6 | Opaque resources use a dedicated vending Knot, not passed directly | Live connections/sessions cannot travel the graph |
| R7 | `__init__` params use Knot types or `Knot \| scalar` — NOT plain scalars | Ensures graph wiring and lineage |
| R8 | If inherits `SubTapestry`: `process()` calls `self._run_inner()` | N/A for plain `Knot`/`Source`/`Sink` |
| R9 | Quality assessment Knots returning `QualityReport` use `*Check` suffix, not `*Gate` | N/A if not a quality assessment Knot |
| R10-Algo | Module docstring contains `Algorithm:` section | Step-by-step description |
| R10-Math | Module docstring contains `Math:` section | N/A if no quantitative computation |
| R10-Refs | Module docstring contains `References:` section | N/A if entirely pirn-native |
| Sec | Any `hashlib.md5()` call includes `usedforsecurity=False` | N/A if no md5 usage |
| Step11 | Tests call `process()` directly with plain values under `tests/unit/` | Not just via Tapestry.run() |
| Step12 | All applicable rules pass AND Step11 passes | Ready for ruff/pyright/pytest |

**Cell values:** `[x]` = compliant · `[ ]` = violation · `N/A` = rule does not apply

---

## Audit Table

### Group 1 — Sources and Sinks

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/sources/file_source.py` | [ ] | [ ] | [ ] | [ ] | [ ] | N/A | [ ] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/sources/directory_source.py` | [ ] | [ ] | [ ] | [ ] | [ ] | N/A | [ ] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/sinks/file_sink.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lakehouse/lakehouse_table_source.py` | [ ] | [ ] | [ ] | [ ] | N/A | N/A | [ ] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lakehouse/lakehouse_table_sink.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |

### Group 2 — Lazy Sources

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/lazy/dask/dask_source.py` | [ ] | [x] | [ ] | [ ] | [ ] | N/A | [ ] | N/A | N/A | [ ] | N/A | [ ] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/ibis/ibis_source.py` | [ ] | [x] | [ ] | [ ] | [ ] | [ ] | [ ] | N/A | N/A | [ ] | N/A | [ ] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/ray/ray_source.py` | [ ] | [x] | [ ] | [ ] | [ ] | N/A | [ ] | N/A | N/A | [ ] | N/A | [ ] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/spark/spark_source.py` | [ ] | [x] | [ ] | [ ] | [ ] | N/A | [ ] | N/A | N/A | [ ] | N/A | [ ] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/cdc/debezium_source.py` | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | N/A | N/A | [ ] | N/A | [ ] | N/A | [x] | [ ] |
| `pirn/domains/data/specialized/eland/eland_source.py` | [ ] | [x] | [ ] | [ ] | [ ] | [ ] | [ ] | N/A | N/A | [ ] | N/A | [ ] | N/A | [x] | [ ] |
| `pirn/domains/data/specialized/lance/lance_source.py` | [ ] | [x] | [ ] | [ ] | [ ] | N/A | [ ] | N/A | N/A | [ ] | N/A | [ ] | N/A | [x] | [ ] |

### Group 3 — DataFusion

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/frames/datafusion/datafusion_session_context_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [ ] | [ ] |
| `pirn/domains/data/frames/datafusion/bridges/data_batch_to_datafusion.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/datafusion/bridges/datafusion_to_data_batch.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/datafusion/datafusion_aggregate.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/datafusion/datafusion_filter.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/datafusion/datafusion_join.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |

### Group 4 — DuckDB

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/frames/duckdb/duckdb_connection_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [ ] | [ ] |
| `pirn/domains/data/frames/duckdb/bridges/data_batch_to_duckdb.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/duckdb/bridges/duckdb_to_data_batch.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | N/A | N/A | N/A | N/A | [x] | [ ] |
| `pirn/domains/data/frames/duckdb/duckdb_aggregate.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/duckdb/duckdb_cast.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/duckdb/duckdb_deduplicate.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/duckdb/duckdb_filter.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/duckdb/duckdb_join.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/duckdb/duckdb_rename.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |

### Group 5 — Pandas

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/frames/pandas/bridges/data_batch_to_pandas.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [ ] | N/A | [ ] | N/A | [ ] | [ ] |
| `pirn/domains/data/frames/pandas/bridges/pandas_to_data_batch.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [ ] | N/A | [ ] | N/A | [ ] | [ ] |
| `pirn/domains/data/frames/pandas/pandas_aggregate.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/pandas/pandas_cast.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/pandas/pandas_deduplicate.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/pandas/pandas_filter.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/pandas/pandas_join.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/pandas/pandas_rename.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |

### Group 6 — Polars

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/frames/polars/bridges/data_batch_to_polars.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [ ] | N/A | N/A | N/A | [x] | [ ] |
| `pirn/domains/data/frames/polars/bridges/polars_to_data_batch.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [ ] | N/A | N/A | N/A | [x] | [ ] |
| `pirn/domains/data/frames/polars/polars_aggregate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/polars/polars_cast.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/polars/polars_deduplicate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/polars/polars_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/polars/polars_join.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/polars/polars_pivot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/polars/polars_rename.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/polars/polars_unpivot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/polars/polars_window_calc.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |

### Group 7 — PyArrow

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/frames/pyarrow/bridges/data_batch_to_pyarrow.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/pyarrow/bridges/pyarrow_to_data_batch.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/pyarrow/pyarrow_aggregate.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/pyarrow/pyarrow_cast.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/pyarrow/pyarrow_deduplicate.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/pyarrow/pyarrow_filter.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/pyarrow/pyarrow_join.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/frames/pyarrow/pyarrow_rename.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |

### Group 8 — Lazy Transforms (Dask, Ibis, Ray, Spark)

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/lazy/dask/dask_aggregate.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/dask/dask_compute.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/dask/dask_filter.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/dask/dask_join.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/ibis/ibis_filter.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/ibis/ibis_group_by_aggregate.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/ibis/ibis_join.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/ibis/ibis_to_table.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/ibis/ibis_window.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/ray/ray_aggregate.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/ray/ray_compute.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/ray/ray_filter.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/ray/ray_map.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/spark/spark_aggregate.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/spark/spark_collect_sink.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/spark/spark_filter.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/spark/spark_join.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/lazy/spark/spark_write_sink.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |

### Group 9 — Quality and Transforms

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/quality/freshness_check.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | [x] | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/quality/null_rate_check.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | [x] | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/quality/profiler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/quality/row_count_check.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | [x] | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/quality/schema_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/transforms/aggregate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/transforms/cast.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/transforms/deduplicate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/transforms/filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/transforms/normalize.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/transforms/rename.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |

### Group 10 — Validation and Specialized (eland, lance)

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/validation/great_expectations/great_expectations_pandas_validator.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/validation/pandera/pandera_pandas_validator.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/validation/pandera/pandera_polars_validator.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specialized/eland/eland_filter.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specialized/eland/eland_to_pandas.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [ ] |
| `pirn/domains/data/specialized/lance/arrow_to_lance_sink.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specialized/lance/lance_to_arrow.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | N/A | N/A | [x] | [ ] |

### Group 11 — Analytics Engineering, Data Vault, Dimensional

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/specializations/analytics_engineering/exposure_lineage_tag.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/analytics_engineering/intermediate_model_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/analytics_engineering/mart_model_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/analytics_engineering/metric_layer_aggregator.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/analytics_engineering/refresh_materialized_view.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/analytics_engineering/staging_model_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/data_vault/data_vault_bridge_table_builder.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/data_vault/data_vault_hub_loader.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/data_vault/data_vault_link_loader.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/data_vault/data_vault_pit_table_builder.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/data_vault/data_vault_satellite_loader.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/dimensional/bridge_table_builder.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/dimensional/date_dim_generator.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/dimensional/dim_table_load.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/dimensional/fact_table_load.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |

### Group 12 — Deduplication, Feature Engineering, Incremental

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/specializations/deduplication/exact_deduplicator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/deduplication/fuzzy_deduplicator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/deduplication/probabilistic_linker.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/deduplication/windowed_deduplicator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/feature_engineering/binning_knot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/feature_engineering/column_hasher.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | [x] | [x] | [ ] |
| `pirn/domains/data/specializations/feature_engineering/date_part_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/feature_engineering/derived_column_calculator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/feature_engineering/geo_enricher.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/feature_engineering/lookup_enricher.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/feature_engineering/string_normalizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/feature_engineering/text_token_counter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [ ] | [ ] |
| `pirn/domains/data/specializations/incremental/database_connection_pool_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [ ] | [ ] |
| `pirn/domains/data/specializations/incremental/dbt_style_snapshot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | [x] | [x] | [ ] |
| `pirn/domains/data/specializations/incremental/delete_safe_sync.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/incremental/merge_upsert.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/incremental/partitioned_overwrite.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/incremental/snapshot_table_appender.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |

### Group 13 — Ingestion, Medallion, Quality Specializations

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/specializations/ingestion/append_only_ingest.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/ingestion/full_refresh_extract.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/ingestion/query_new_rows_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/ingestion/read_high_water_mark_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/ingestion/rows_behind_truncate_check_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | N/A | N/A | N/A | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/ingestion/truncate_table_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/ingestion/watermark_incremental_extract.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/medallion/bronze_raw_ingest.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/medallion/data_batch_to_tuples_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/medallion/gold_aggregation.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/medallion/silver_clean_transform.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/medallion/stamp_bronze_metadata_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/medallion/tuples_to_data_batch_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/quality/freshness_check.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/quality/null_rate_monitor.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/quality/reconciliation_diff.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | [x] | [x] | [ ] |
| `pirn/domains/data/specializations/quality/referential_integrity_check.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/quality/row_count_anomaly_detector.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/quality/schema_evolution_detector.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/quality/statistical_profiler.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |

### Group 14 — SCD, Schema Migration, Timeseries

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| `pirn/domains/data/specializations/scd/cdc_debezium.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/scd_type_1.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/scd_type_1_merge_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/scd_type_1_overwrite.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/scd_type_2.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/scd_type_2_history.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/scd_type_2_merge_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/scd_type_3_previous_value.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/scd_type_4_mini_dimension.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/scd_type_5_mini_dim_with_current.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/scd_type_6_hybrid.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/scd_type_7.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/scd_type_7_hybrid.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/scd/scd_type_7_merge_knot.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/schema_migration/backfill_runner.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/schema_migration/column_lineage_tracker.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | N/A | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/schema_migration/schema_version_migrator.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/timeseries/cohort_aggregator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/timeseries/funnel_analysis_knot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/timeseries/late_arriving_event_handler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/timeseries/rolling_window_aggregator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/timeseries/sessionization_knot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [ ] |
| `pirn/domains/data/specializations/timeseries/time_series_resampler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [ ] |

---

## Violations Summary

**17 files with open violations (Step12 not ready):**

### Structural violations (Groups 1–2) — require full remediation

| File | Open Rules |
|------|-----------|
| `sources/file_source.py` | R1 R2 R3 R4 R5 R7 |
| `sources/directory_source.py` | R1 R2 R3 R4 R5 R7 |
| `lakehouse/lakehouse_table_source.py` | R1 R2 R3 R4 R7 |
| `lazy/dask/dask_source.py` | R1 R3 R4 R5 R7 R10-Algo R10-Refs |
| `lazy/ibis/ibis_source.py` | R1 R3 R4 R5 R6 R7 R10-Algo R10-Refs |
| `lazy/ray/ray_source.py` | R1 R3 R4 R5 R7 R10-Algo R10-Refs |
| `lazy/spark/spark_source.py` | R1 R3 R4 R5 R7 R10-Algo R10-Refs |
| `scd/cdc/debezium_source.py` | R1 R2 R3 R4 R5 R6 R7 R10-Algo R10-Refs |
| `specialized/eland/eland_source.py` | R1 R3 R4 R5 R6 R7 R10-Algo R10-Refs |
| `specialized/lance/lance_source.py` | R1 R3 R4 R5 R7 R10-Algo R10-Refs |

### Documentation / test violations only — minor fixes

| File | Open Rules |
|------|-----------|
| `datafusion/datafusion_session_context_knot.py` | Step11 |
| `pandas/bridges/data_batch_to_pandas.py` | R10-Algo R10-Refs Step11 |
| `pandas/bridges/pandas_to_data_batch.py` | R10-Algo R10-Refs Step11 |
| `polars/bridges/data_batch_to_polars.py` | R10-Algo |
| `polars/bridges/polars_to_data_batch.py` | R10-Algo |
| `feature_engineering/text_token_counter.py` | Step11 |
| `incremental/database_connection_pool_knot.py` | Step11 |

---

## Remediation Order

1. **Create vending Knots first** (required before fixing consumers):
   - `IbisConnectionKnot` — for `ibis_source.py`
   - `SparkSessionKnot` — for `spark_source.py` (if spark_session is opaque)
   - `MessageBrokerKnot` — for `debezium_source.py`
   - `ElasticsearchClientKnot` — for `eland_source.py`

2. **Fix structural violations** (Groups 1–2, 10 files)

3. **Add docstrings / tests** (7 files — no structural changes needed)
