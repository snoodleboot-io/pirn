# Knot Remediation Execution Plan

**Branch:** feat/domain-knot-libraries  
**Started:** 2026-05-05  
**Rules:** docs/contributing/knot-design-rules.md  
**Process:** docs/contributing/knot-remediation-process.md  
**Audit:** `uv run python scripts/audit_knots.py`

Commit grouping: one commit per new vending Knot; one commit per rename sweep; one commit per domain/sub-domain.

Per-file checklist (all 12 process steps):
- Step 1: Inventory violations
- Step 2: Determine two-layer signature
- Step 3: Create vending Knots first (if needed)
- Step 4: Rewrite `__init__` as pure wiring call
- Step 5: Rewrite `process()` to declare all inputs with value types
- Step 6: Move validation into `process()` or private helpers
- Step 7: Remove `self._x` and `@property` fields
- Step 8: Fix inheritance (`SubTapestry` → `Knot` if no `_run_inner`)
- Step 9: Rename if needed (`*Gate` → `*Check`)
- Step 10: Add Algorithm / Math (if quantitative) / References docstring sections
- Step 11: Tests — happy path, validation errors, scalar-input wiring, knot-input wiring
- Step 12: Verify — `ruff`, `pyright`, `pytest` all pass

---

## Phase 1 — Vending Knots

- [x] `pirn/domains/data/frames/datafusion/datafusion_session_context_knot.py` — steps 1–12
- [x] `pirn/domains/data/frames/duckdb/duckdb_connection_knot.py` — steps 1–12
- [x] `pirn/domains/data/specializations/incremental/database_connection_pool_knot.py` — steps 1–12
- [x] **Commit:** `feat: add vending Knots for DataFusion, DuckDB, and DatabaseConnectionPool`

---

## Phase 2 — Renames

> Renames only — no process compliance on the renamed files. Full remediation in Phase 5.

- [x] `pirn/domains/data/quality/freshness_gate.py` → `freshness_check.py` (`FreshnessGate` → `FreshnessCheck`)
- [x] `pirn/domains/data/quality/null_rate_gate.py` → `null_rate_check.py` (`NullRateGate` → `NullRateCheck`)
- [x] `pirn/domains/data/quality/row_count_gate.py` → `row_count_check.py` (`RowCountGate` → `RowCountCheck`)
- [x] Update `pirn/domains/data/quality/__init__.py` exports
- [x] Update `pirn/domains/data/quality/profiler.py` docstring stale refs
- [x] `pirn/domains/data/specializations/ingestion/gate_rows_behind_truncate_knot.py` → `rows_behind_truncate_check_knot.py`
- [x] Update all import refs and tests for renamed files
- [x] **Commit:** `feat: rename *Gate quality knots to *Check and fix ingestion knot name`

---

## Phase 3 — DataFusion Frames

- [x] `pirn/domains/data/frames/datafusion/bridges/data_batch_to_datafusion.py` — steps 1–12
- [x] `pirn/domains/data/frames/datafusion/bridges/datafusion_to_data_batch.py` — steps 1–12 (Algorithm + References; TestWiring via bridges test)
- [x] `pirn/domains/data/frames/datafusion/datafusion_filter.py` — steps 1–12 (no Math; TestWiring: predicate from knot)
- [x] `pirn/domains/data/frames/datafusion/datafusion_join.py` — steps 1–12 (no Math; TestWiring: how from knot)
- [x] `pirn/domains/data/frames/datafusion/datafusion_aggregate.py` — steps 1–12 (no Math; TestWiring: by from knot)
- [x] `pirn/domains/data/frames/datafusion/datafusion_data_batch.py` — not a Knot (frozen dataclass); out of scope

---

## Phase 4 — PyArrow Frames

- [x] `pirn/domains/data/frames/pyarrow/pyarrow_filter.py` — steps 1–12 (no Math — no quantitative computation)
- [x] `pirn/domains/data/frames/pyarrow/pyarrow_join.py` — steps 1–12 (no Math — no quantitative computation)
- [x] `pirn/domains/data/frames/pyarrow/pyarrow_aggregate.py` — steps 1–12 (no Math — user-supplied kernels)
- [x] `pirn/domains/data/frames/pyarrow/pyarrow_deduplicate.py` — steps 1–12 (Math: first-occurrence index formula)
- [x] `pirn/domains/data/frames/pyarrow/pyarrow_rename.py` — steps 1–12 (no Math)
- [x] `pirn/domains/data/frames/pyarrow/pyarrow_cast.py` — steps 1–12 (no Math)
- [x] `pirn/domains/data/frames/pyarrow/pyarrow_data_batch.py` — not a Knot (frozen dataclass); out of scope for remediation
- [x] Update pyarrow tests — TestValidation + TestWiring on all 6 Knot files

---

## Phase 5 — Quality Domain (full remediation, including Phase 2 renamed files)

- [x] `pirn/domains/data/quality/freshness_check.py` — steps 1–12 (Math: age ≤ max_age; TestWiring: column + max_age from knot)
- [x] `pirn/domains/data/quality/null_rate_check.py` — steps 1–12 (Math: null_rate = null_count/N; TestWiring: thresholds from knot)
- [x] `pirn/domains/data/quality/row_count_check.py` — steps 1–12 (Math: min ≤ N ≤ max; TestWiring: min_rows + max_rows from knot)
- [x] `pirn/domains/data/quality/schema_validator.py` — steps 1–12 (no Math; TestWiring: schema from knot)
- [x] `pirn/domains/data/quality/profiler.py` — steps 1–12 (no Math; TestWiring: columns from knot)
- [x] **Commit:** `fix: remediate quality domain knots`

---

## Phase 6 — File Source / Sink

- [x] `pirn/domains/data/sources/file_source.py` — full steps 1–12 (Source base; config stored in __init__; Algorithm + References)
- [x] `pirn/domains/data/sources/directory_source.py` — full steps 1–12 (Source base; no TestWiring — Sources have no upstream knot inputs)
- [x] `pirn/domains/data/sinks/file_sink.py` — full steps 1–12 (Sink base; two-layer signature; TestWiring: key from knot)
- [x] `pirn/domains/data/specialized/lance/arrow_to_lance_sink.py` — full steps 1–12 (Sink base; two-layer signature; TestWiring: path from knot)
- [x] Update tests — TestValidation + TestFileSink/TestFileSink + TestWiring (41 tests passing)
- [ ] **Commit:** `fix: remediate file source and sink knots`

---

## Phase 7 — Incremental Specializations

- [x] `pirn/domains/data/specializations/incremental/merge_upsert.py` — steps 1–12 (SubTapestry → Knot; @property → @staticmethod; two-layer signature)
- [x] `pirn/domains/data/specializations/incremental/dbt_style_snapshot.py` — steps 1–12 (hashlib.md5 usedforsecurity=False; Math section)
- [x] `pirn/domains/data/specializations/incremental/delete_safe_sync.py` — steps 1–12
- [x] `pirn/domains/data/specializations/incremental/partitioned_overwrite.py` — steps 1–12
- [x] `pirn/domains/data/specializations/incremental/snapshot_table_appender.py` — steps 1–12
- [x] Update incremental tests — TestXxx + TestWiring + TestValidation (39 tests passing)
- [ ] **Commit:** `fix: remediate incremental specialization knots`

---

## Phase 8 — Broader Specializations (SubTapestry → Knot)

### analytics_engineering
- [ ] `exposure_lineage_tag.py` — full steps 1–12
- [ ] `intermediate_model_knot.py` — full steps 1–12
- [ ] `mart_model_knot.py` — full steps 1–12
- [ ] `metric_layer_aggregator.py` — full steps 1–12
- [ ] `refresh_materialized_view.py` — full steps 1–12
- [ ] `staging_model_knot.py` — full steps 1–12
- [ ] **Commit:** `fix: remediate analytics_engineering specialization knots`

### data_vault
- [ ] `data_vault_hub_loader.py` — full steps 1–12
- [ ] `data_vault_link_loader.py` — full steps 1–12
- [ ] `data_vault_satellite_loader.py` — full steps 1–12
- [ ] `data_vault_bridge_table_builder.py` — full steps 1–12
- [ ] `data_vault_pit_table_builder.py` — full steps 1–12
- [ ] **Commit:** `fix: remediate data_vault specialization knots`

### deduplication
- [ ] `exact_deduplicator.py` — full steps 1–12
- [ ] `fuzzy_deduplicator.py` — full steps 1–12
- [ ] `probabilistic_linker.py` — full steps 1–12
- [ ] `windowed_deduplicator.py` — full steps 1–12
- [ ] **Commit:** `fix: remediate deduplication specialization knots`

### dimensional
- [ ] `date_dim_generator.py` — full steps 1–12
- [ ] `dim_table_load.py` — full steps 1–12
- [ ] `fact_table_load.py` — full steps 1–12
- [ ] `bridge_table_builder.py` — full steps 1–12
- [ ] **Commit:** `fix: remediate dimensional specialization knots`

### feature_engineering
- [ ] `binning_knot.py` — full steps 1–12
- [ ] `column_hasher.py` — full steps 1–12
- [ ] `date_part_extractor.py` — full steps 1–12
- [ ] `derived_column_calculator.py` — full steps 1–12
- [ ] `geo_enricher.py` — full steps 1–12
- [ ] `lookup_enricher.py` — full steps 1–12
- [ ] `string_normalizer.py` — full steps 1–12
- [ ] `text_token_counter.py` — full steps 1–12
- [ ] **Commit:** `fix: remediate feature_engineering specialization knots`

### ingestion (remaining after Phase 2 rename)
- [ ] `append_only_ingest.py` — full steps 1–12
- [ ] `full_refresh_extract.py` — full steps 1–12
- [ ] `query_new_rows_knot.py` — full steps 1–12
- [ ] `read_high_water_mark_knot.py` — full steps 1–12
- [ ] `rows_behind_truncate_check_knot.py` — full steps 1–12
- [ ] `truncate_table_knot.py` — full steps 1–12
- [ ] `watermark_incremental_extract.py` — full steps 1–12
- [ ] **Commit:** `fix: remediate ingestion specialization knots`

### medallion
- [ ] `bronze_raw_ingest.py` — full steps 1–12
- [ ] `data_batch_to_tuples_knot.py` — full steps 1–12
- [ ] `gold_aggregation.py` — full steps 1–12
- [ ] `silver_clean_transform.py` — full steps 1–12
- [ ] `stamp_bronze_metadata_knot.py` — full steps 1–12
- [ ] `tuples_to_data_batch_knot.py` — full steps 1–12
- [ ] **Commit:** `fix: remediate medallion specialization knots`

### quality (specializations)
- [ ] `freshness_check.py` — full steps 1–12
- [ ] `null_rate_monitor.py` — full steps 1–12
- [ ] `reconciliation_diff.py` — full steps 1–12
- [ ] `referential_integrity_check.py` — full steps 1–12
- [ ] `row_count_anomaly_detector.py` — full steps 1–12
- [ ] `schema_evolution_detector.py` — full steps 1–12
- [ ] `statistical_profiler.py` — full steps 1–12
- [ ] **Commit:** `fix: remediate quality specialization knots`

### scd
- [ ] `scd_type_1.py` — full steps 1–12
- [ ] `scd_type_1_merge_knot.py` — full steps 1–12
- [ ] `scd_type_1_overwrite.py` — full steps 1–12
- [ ] `scd_type_2.py` — full steps 1–12
- [ ] `scd_type_2_history.py` — full steps 1–12
- [ ] `scd_type_2_merge_knot.py` — full steps 1–12
- [ ] `scd_type_3_previous_value.py` — full steps 1–12
- [ ] `scd_type_4_mini_dimension.py` — full steps 1–12
- [ ] `scd_type_5_mini_dim_with_current.py` — full steps 1–12
- [ ] `scd_type_6_hybrid.py` — full steps 1–12
- [ ] `scd_type_7.py` — full steps 1–12
- [ ] `scd_type_7_hybrid.py` — full steps 1–12
- [ ] `scd_type_7_merge_knot.py` — full steps 1–12
- [ ] `cdc/cdc_debezium.py` — full steps 1–12
- [ ] **Commit:** `fix: remediate scd specialization knots`

### schema_migration
- [ ] `backfill_runner.py` — full steps 1–12
- [ ] `column_lineage_tracker.py` — full steps 1–12
- [ ] `schema_version_migrator.py` — full steps 1–12
- [ ] **Commit:** `fix: remediate schema_migration specialization knots`

### timeseries
- [ ] `cohort_aggregator.py` — full steps 1–12
- [ ] `funnel_analysis_knot.py` — full steps 1–12
- [ ] `late_arriving_event_handler.py` — full steps 1–12
- [ ] `rolling_window_aggregator.py` — full steps 1–12
- [ ] `sessionization_knot.py` — full steps 1–12
- [ ] `time_series_resampler.py` — full steps 1–12
- [ ] **Commit:** `fix: remediate timeseries specialization knots`

---

## Phase 9 — Lakehouse Base Class Consistency

- [ ] `pirn/domains/data/frames/lakehouse/lakehouse_table_source.py` — change base `Knot` → `Source`; full steps 1–12
- [ ] `pirn/domains/data/frames/lakehouse/lakehouse_table_sink.py` — change base `Knot` → `Sink`; full steps 1–12
- [ ] Update tests — all four scenario types
- [ ] **Commit:** `fix: align LakehouseTableSource/Sink with Source/Sink base classes`

---

## Final Verification

- [ ] Run `uv run python scripts/audit_knots.py --path pirn/domains/data` — expect zero violations
- [ ] Run `uv run ruff check pirn/domains/data/`
- [ ] Run `uv run pyright pirn/domains/data/` — `reportIncompatibleMethodOverride` on `process()` is a known pre-existing baseline across all domain Knots (framework variadic design); treat as suppressed, do not introduce per-file directives
- [ ] Run `uv run pytest tests/unit/ -x -q`
