# Knot Remediation — Remaining Files Checklist

Process: `docs/contributing/knot-remediation-process.md` (Steps 1–12)

Each file must complete ALL 12 steps before being marked `[x]`.

Steps per file:
1. Inventory violations
2. Determine two-layer signature
3. Create vending Knots for opaque resources (if needed)
4. Rewrite `__init__` as pure wiring call
5. Rewrite `process()` to declare all inputs
6. Move validation into `process()` or private helpers
7. Remove `self._x` attributes and `@property` fields
8. Fix inheritance if needed (SubTapestry → Knot)
9. Rename if needed (`*Gate` → `*Check`)
10. Add Algorithm, Math, References docstring sections
11. Update tests (happy path, validation errors, scalar wiring, Knot wiring)
12. Verify: `ruff check`, `pyright`, `pytest tests/unit/ -x -q`

---

## Group A — frames/duckdb (7 files)

- [x] `pirn/domains/data/frames/duckdb/bridges/data_batch_to_duckdb.py`
  - tests: `tests/unit/domains/data/frames/duckdb/bridges/`
- [x] `pirn/domains/data/frames/duckdb/duckdb_aggregate.py`
  - tests: `tests/unit/domains/data/frames/duckdb/test_duckdb_aggregate.py`
- [x] `pirn/domains/data/frames/duckdb/duckdb_cast.py`
  - tests: `tests/unit/domains/data/frames/duckdb/test_duckdb_cast.py`
- [x] `pirn/domains/data/frames/duckdb/duckdb_deduplicate.py`
  - tests: `tests/unit/domains/data/frames/duckdb/test_duckdb_deduplicate.py`
- [x] `pirn/domains/data/frames/duckdb/duckdb_filter.py`
  - tests: `tests/unit/domains/data/frames/duckdb/test_duckdb_filter.py`
- [x] `pirn/domains/data/frames/duckdb/duckdb_join.py`
  - tests: `tests/unit/domains/data/frames/duckdb/test_duckdb_join.py`
- [x] `pirn/domains/data/frames/duckdb/duckdb_rename.py`
  - tests: `tests/unit/domains/data/frames/duckdb/test_duckdb_rename.py`
- [ ] **Commit:** `fix: remediate frames/duckdb knots (steps 1–12)`

---

## Group B — frames/pandas (6 files)

- [ ] `pirn/domains/data/frames/pandas/pandas_aggregate.py`
  - tests: `tests/unit/domains/data/frames/pandas/test_pandas_aggregate.py`
- [ ] `pirn/domains/data/frames/pandas/pandas_cast.py`
  - tests: `tests/unit/domains/data/frames/pandas/test_pandas_cast.py`
- [ ] `pirn/domains/data/frames/pandas/pandas_deduplicate.py`
  - tests: `tests/unit/domains/data/frames/pandas/test_pandas_deduplicate.py`
- [ ] `pirn/domains/data/frames/pandas/pandas_filter.py`
  - tests: `tests/unit/domains/data/frames/pandas/test_pandas_filter.py`
- [ ] `pirn/domains/data/frames/pandas/pandas_join.py`
  - tests: `tests/unit/domains/data/frames/pandas/test_pandas_join.py`
- [ ] `pirn/domains/data/frames/pandas/pandas_rename.py`
  - tests: `tests/unit/domains/data/frames/pandas/test_pandas_rename.py`
- [ ] **Commit:** `fix: remediate frames/pandas knots (steps 1–12)`

---

## Group C — frames/polars (9 files)

- [ ] `pirn/domains/data/frames/polars/polars_aggregate.py`
  - tests: `tests/unit/domains/data/frames/polars/test_polars_aggregate.py`
- [ ] `pirn/domains/data/frames/polars/polars_cast.py`
  - tests: `tests/unit/domains/data/frames/polars/test_polars_cast.py`
- [ ] `pirn/domains/data/frames/polars/polars_deduplicate.py`
  - tests: `tests/unit/domains/data/frames/polars/test_polars_deduplicate.py`
- [ ] `pirn/domains/data/frames/polars/polars_filter.py`
  - tests: `tests/unit/domains/data/frames/polars/test_polars_filter.py`
- [ ] `pirn/domains/data/frames/polars/polars_join.py`
  - tests: `tests/unit/domains/data/frames/polars/test_polars_join.py`
- [ ] `pirn/domains/data/frames/polars/polars_pivot.py`
  - tests: `tests/unit/domains/data/frames/polars/test_polars_pivot.py`
- [ ] `pirn/domains/data/frames/polars/polars_rename.py`
  - tests: `tests/unit/domains/data/frames/polars/test_polars_rename.py`
- [ ] `pirn/domains/data/frames/polars/polars_unpivot.py`
  - tests: `tests/unit/domains/data/frames/polars/test_polars_unpivot.py`
- [ ] `pirn/domains/data/frames/polars/polars_window_calc.py`
  - tests: `tests/unit/domains/data/frames/polars/test_polars_window_calc.py`
- [ ] **Commit:** `fix: remediate frames/polars knots (steps 1–12)`

---

## Group D — lazy/dask (4 files, excluding DaskSource)

- [x] `pirn/domains/data/lazy/dask/dask_aggregate.py`
  - tests: `tests/unit/domains/data/lazy/dask/test_dask_aggregate.py`
- [x] `pirn/domains/data/lazy/dask/dask_compute.py`
  - tests: `tests/unit/domains/data/lazy/dask/test_dask_compute.py`
- [x] `pirn/domains/data/lazy/dask/dask_filter.py`
  - tests: `tests/unit/domains/data/lazy/dask/test_dask_filter.py`
- [x] `pirn/domains/data/lazy/dask/dask_join.py`
  - tests: `tests/unit/domains/data/lazy/dask/test_dask_join.py`
- [x] **Commit:** `fix: remediate lazy/dask knots (steps 1–12)`

---

## Group E — lazy/ibis (5 files, excluding IbisSource)

- [x] `pirn/domains/data/lazy/ibis/ibis_filter.py`
  - tests: `tests/unit/domains/data/lazy/ibis/test_ibis_filter.py`
- [x] `pirn/domains/data/lazy/ibis/ibis_group_by_aggregate.py`
  - tests: `tests/unit/domains/data/lazy/ibis/test_ibis_group_by_aggregate.py`
- [x] `pirn/domains/data/lazy/ibis/ibis_join.py`
  - tests: `tests/unit/domains/data/lazy/ibis/test_ibis_join.py`
- [x] `pirn/domains/data/lazy/ibis/ibis_to_table.py`
  - tests: `tests/unit/domains/data/lazy/ibis/test_ibis_to_table.py`
- [x] `pirn/domains/data/lazy/ibis/ibis_window.py`
  - tests: `tests/unit/domains/data/lazy/ibis/test_ibis_window.py`
- [x] **Commit:** `fix: remediate lazy/ibis knots (steps 1–12)`

---

## Group F — lazy/ray (4 files, excluding RaySource)

- [ ] `pirn/domains/data/lazy/ray/ray_aggregate.py`
  - tests: `tests/unit/domains/data/lazy/ray/test_ray_aggregate.py`
- [ ] `pirn/domains/data/lazy/ray/ray_compute.py`
  - tests: `tests/unit/domains/data/lazy/ray/test_ray_compute.py`
- [ ] `pirn/domains/data/lazy/ray/ray_filter.py`
  - tests: `tests/unit/domains/data/lazy/ray/test_ray_filter.py`
- [ ] `pirn/domains/data/lazy/ray/ray_map.py`
  - tests: `tests/unit/domains/data/lazy/ray/test_ray_map.py`
- [ ] **Commit:** `fix: remediate lazy/ray knots (steps 1–12)`

---

## Group G — lazy/spark (5 files, excluding SparkSource)

- [ ] `pirn/domains/data/lazy/spark/spark_aggregate.py`
  - tests: `tests/unit/domains/data/lazy/spark/test_spark_aggregate.py`
- [ ] `pirn/domains/data/lazy/spark/spark_collect_sink.py`
  - tests: `tests/unit/domains/data/lazy/spark/test_spark_collect_sink.py`
- [ ] `pirn/domains/data/lazy/spark/spark_filter.py`
  - tests: `tests/unit/domains/data/lazy/spark/test_spark_filter.py`
- [ ] `pirn/domains/data/lazy/spark/spark_join.py`
  - tests: `tests/unit/domains/data/lazy/spark/test_spark_join.py`
- [ ] `pirn/domains/data/lazy/spark/spark_write_sink.py`
  - tests: `tests/unit/domains/data/lazy/spark/test_spark_write_sink.py`
- [ ] **Commit:** `fix: remediate lazy/spark knots (steps 1–12)`

---

## Group H — specialized/eland (1 file, excluding ElandSource)

- [ ] `pirn/domains/data/specialized/eland/eland_filter.py`
  - tests: `tests/unit/domains/data/specialized/eland/test_eland_filter.py`
- [ ] **Commit:** `fix: remediate specialized/eland knots (steps 1–12)`

---

## Group I — transforms (6 files)

- [ ] `pirn/domains/data/transforms/aggregate.py`
  - tests: `tests/unit/domains/data/transforms/test_aggregate.py`
- [ ] `pirn/domains/data/transforms/cast.py`
  - tests: `tests/unit/domains/data/transforms/test_cast.py`
- [ ] `pirn/domains/data/transforms/deduplicate.py`
  - tests: `tests/unit/domains/data/transforms/test_deduplicate.py`
- [ ] `pirn/domains/data/transforms/filter.py`
  - tests: `tests/unit/domains/data/transforms/test_filter.py`
- [ ] `pirn/domains/data/transforms/normalize.py`
  - tests: `tests/unit/domains/data/transforms/test_normalize.py`
- [ ] `pirn/domains/data/transforms/rename.py`
  - tests: `tests/unit/domains/data/transforms/test_rename.py`
- [ ] **Commit:** `fix: remediate transforms knots (steps 1–12)`

---

## Group J — validation (3 files)

- [ ] `pirn/domains/data/validation/great_expectations/great_expectations_pandas_validator.py`
  - tests: `tests/unit/domains/data/validation/great_expectations/`
- [ ] `pirn/domains/data/validation/pandera/pandera_pandas_validator.py`
  - tests: `tests/unit/domains/data/validation/pandera/`
- [ ] `pirn/domains/data/validation/pandera/pandera_polars_validator.py`
  - tests: `tests/unit/domains/data/validation/pandera/`
- [ ] **Commit:** `fix: remediate validation knots (steps 1–12)`

---

## Final verification

- [ ] `python -c "import subprocess; r = subprocess.run(['python', 'scripts/audit_knots.py', '--path', 'pirn/domains/data'], capture_output=True, text=True); print(r.stdout)"` — 0 non-Source violations
- [ ] `uv run ruff check pirn/domains/data/`
- [ ] `python -m pytest tests/unit/domains/data/ -x -q`
