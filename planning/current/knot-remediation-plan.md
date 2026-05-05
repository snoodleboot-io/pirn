# Knot Remediation Execution Plan

**Branch:** feat/domain-knot-libraries  
**Started:** 2026-05-05  
**Rules:** docs/contributing/knot-design-rules.md  
**Process:** docs/contributing/knot-remediation-process.md  
**Audit:** `uv run python scripts/audit_knots.py`

Commit grouping: one commit per new vending Knot; one commit per rename sweep; one commit per domain/sub-domain.

---

## Phase 1 — Vending Knots

- [ ] Create `pirn/domains/data/frames/datafusion/datafusion_session_context_knot.py` — `DatafusionSessionContextKnot`
- [ ] Create `pirn/domains/data/frames/duckdb/duckdb_connection_knot.py` — `DuckDBConnectionKnot`
- [ ] Create `pirn/domains/data/specializations/incremental/database_connection_pool_knot.py` — `DatabaseConnectionPoolKnot`
- [ ] **Commit:** `feat: add vending Knots for DataFusion, DuckDB, and DatabaseConnectionPool`

---

## Phase 2 — Renames

- [ ] `pirn/domains/data/quality/freshness_gate.py` → `freshness_check.py` (`FreshnessGate` → `FreshnessCheck`)
- [ ] `pirn/domains/data/quality/null_rate_gate.py` → `null_rate_check.py` (`NullRateGate` → `NullRateCheck`)
- [ ] `pirn/domains/data/quality/row_count_gate.py` → `row_count_check.py` (`RowCountGate` → `RowCountCheck`)
- [ ] Update `pirn/domains/data/quality/__init__.py` exports
- [ ] Update `pirn/domains/data/quality/profiler.py` docstring stale refs
- [ ] `pirn/domains/data/specializations/ingestion/gate_rows_behind_truncate_knot.py` → `rows_behind_truncate_check_knot.py` (rename class + file)
- [ ] Update all import refs and tests for renamed files
- [ ] **Commit:** `feat: rename *Gate quality knots to *Check and fix ingestion knot name`

---

## Phase 3 — DataFusion Frames

- [ ] `pirn/domains/data/frames/datafusion/bridges/data_batch_to_datafusion.py` — remove `self._context`, wire `DatafusionSessionContextKnot`
- [ ] `pirn/domains/data/frames/datafusion/bridges/datafusion_to_data_batch.py` — audit and remediate
- [ ] `pirn/domains/data/frames/datafusion/datafusion_filter.py` — remove `self._predicate`, `self._expression`, `@property`, move validation to `process()`
- [ ] `pirn/domains/data/frames/datafusion/datafusion_join.py` — remediate
- [ ] `pirn/domains/data/frames/datafusion/datafusion_aggregate.py` — remediate
- [ ] `pirn/domains/data/frames/datafusion/datafusion_data_batch.py` — audit and remediate
- [ ] Update datafusion `__init__.py` exports
- [ ] Update datafusion tests
- [ ] **Commit:** `feat: remediate datafusion frames domain knots`

---

## Phase 4 — PyArrow Frames

- [ ] `pirn/domains/data/frames/pyarrow/pyarrow_cast.py` — move `_normalise_dtype` call out of `__init__`, add to `process()`
- [ ] `pirn/domains/data/frames/pyarrow/pyarrow_filter.py` — remediate
- [ ] `pirn/domains/data/frames/pyarrow/pyarrow_join.py` — remediate
- [ ] `pirn/domains/data/frames/pyarrow/pyarrow_aggregate.py` — remediate
- [ ] `pirn/domains/data/frames/pyarrow/pyarrow_deduplicate.py` — remediate
- [ ] `pirn/domains/data/frames/pyarrow/pyarrow_rename.py` — remediate
- [ ] `pirn/domains/data/frames/pyarrow/pyarrow_data_batch.py` — audit
- [ ] Update pyarrow `__init__.py` exports and tests
- [ ] **Commit:** `feat: remediate pyarrow frames domain knots`

---

## Phase 5 — Quality Domain

- [ ] `pirn/domains/data/quality/freshness_check.py` — full remediation (post-rename)
- [ ] `pirn/domains/data/quality/null_rate_check.py` — full remediation (post-rename)
- [ ] `pirn/domains/data/quality/row_count_check.py` — full remediation (post-rename)
- [ ] `pirn/domains/data/quality/schema_validator.py` — remediate
- [ ] `pirn/domains/data/quality/profiler.py` — remediate + update stale Gate refs in docstrings
- [ ] Update quality tests
- [ ] **Commit:** `feat: remediate quality domain knots`

---

## Phase 6 — File Source / Sink

- [ ] `pirn/domains/data/sources/file_source.py` — remediate
- [ ] `pirn/domains/data/sources/directory_source.py` — audit and remediate
- [ ] `pirn/domains/data/sinks/file_sink.py` — remediate
- [ ] Update tests
- [ ] **Commit:** `feat: remediate file source and sink knots`

---

## Phase 7 — Incremental Specializations

- [ ] `pirn/domains/data/specializations/incremental/merge_upsert.py` — `SubTapestry` → `Knot`, wire `DatabaseConnectionPoolKnot`, `@property` → `@staticmethod`, `hashlib.md5` flag
- [ ] `pirn/domains/data/specializations/incremental/dbt_style_snapshot.py` — same pattern + `usedforsecurity=False`
- [ ] `pirn/domains/data/specializations/incremental/delete_safe_sync.py` — remediate
- [ ] `pirn/domains/data/specializations/incremental/partitioned_overwrite.py` — remediate
- [ ] `pirn/domains/data/specializations/incremental/snapshot_table_appender.py` — remediate
- [ ] Update incremental tests
- [ ] **Commit:** `feat: remediate incremental specialization knots`

---

## Phase 8 — Broader Specializations (SubTapestry → Knot)

### analytics_engineering
- [ ] `exposure_lineage_tag.py`
- [ ] `intermediate_model_knot.py`
- [ ] `mart_model_knot.py`
- [ ] `metric_layer_aggregator.py`
- [ ] `refresh_materialized_view.py`
- [ ] `staging_model_knot.py`
- [ ] **Commit:** `feat: remediate analytics_engineering specialization knots`

### data_vault
- [ ] `data_vault_hub_loader.py`
- [ ] `data_vault_link_loader.py`
- [ ] `data_vault_satellite_loader.py`
- [ ] `data_vault_bridge_table_builder.py`
- [ ] `data_vault_pit_table_builder.py`
- [ ] **Commit:** `feat: remediate data_vault specialization knots`

### deduplication
- [ ] `exact_deduplicator.py`
- [ ] `fuzzy_deduplicator.py`
- [ ] `probabilistic_linker.py`
- [ ] `windowed_deduplicator.py`
- [ ] **Commit:** `feat: remediate deduplication specialization knots`

### dimensional
- [ ] `date_dim_generator.py`
- [ ] `dim_table_load.py`
- [ ] `fact_table_load.py`
- [ ] `bridge_table_builder.py`
- [ ] **Commit:** `feat: remediate dimensional specialization knots`

### feature_engineering
- [ ] `binning_knot.py`
- [ ] `column_hasher.py`
- [ ] `date_part_extractor.py`
- [ ] `derived_column_calculator.py`
- [ ] `geo_enricher.py`
- [ ] `lookup_enricher.py`
- [ ] `string_normalizer.py`
- [ ] `text_token_counter.py`
- [ ] **Commit:** `feat: remediate feature_engineering specialization knots`

### ingestion (remaining after Phase 2 rename)
- [ ] `append_only_ingest.py`
- [ ] `full_refresh_extract.py`
- [ ] `query_new_rows_knot.py`
- [ ] `read_high_water_mark_knot.py`
- [ ] `rows_behind_truncate_check_knot.py`
- [ ] `truncate_table_knot.py`
- [ ] `watermark_incremental_extract.py`
- [ ] **Commit:** `feat: remediate ingestion specialization knots`

### medallion
- [ ] `bronze_raw_ingest.py`
- [ ] `data_batch_to_tuples_knot.py`
- [ ] `gold_aggregation.py`
- [ ] `silver_clean_transform.py`
- [ ] `stamp_bronze_metadata_knot.py`
- [ ] `tuples_to_data_batch_knot.py`
- [ ] **Commit:** `feat: remediate medallion specialization knots`

### quality (specializations)
- [ ] `freshness_check.py`
- [ ] `null_rate_monitor.py`
- [ ] `reconciliation_diff.py`
- [ ] `referential_integrity_check.py`
- [ ] `row_count_anomaly_detector.py`
- [ ] `schema_evolution_detector.py`
- [ ] `statistical_profiler.py`
- [ ] **Commit:** `feat: remediate quality specialization knots`

### scd
- [ ] `scd_type_1.py`
- [ ] `scd_type_1_merge_knot.py`
- [ ] `scd_type_1_overwrite.py`
- [ ] `scd_type_2.py`
- [ ] `scd_type_2_history.py`
- [ ] `scd_type_2_merge_knot.py`
- [ ] `scd_type_3_previous_value.py`
- [ ] `scd_type_4_mini_dimension.py`
- [ ] `scd_type_5_mini_dim_with_current.py`
- [ ] `scd_type_6_hybrid.py`
- [ ] `scd_type_7.py`
- [ ] `scd_type_7_hybrid.py`
- [ ] `scd_type_7_merge_knot.py`
- [ ] `cdc/cdc_debezium.py`
- [ ] **Commit:** `feat: remediate scd specialization knots`

### schema_migration
- [ ] `backfill_runner.py`
- [ ] `column_lineage_tracker.py`
- [ ] `schema_version_migrator.py`
- [ ] **Commit:** `feat: remediate schema_migration specialization knots`

### timeseries
- [ ] `cohort_aggregator.py`
- [ ] `funnel_analysis_knot.py`
- [ ] `late_arriving_event_handler.py`
- [ ] `rolling_window_aggregator.py`
- [ ] `sessionization_knot.py`
- [ ] `time_series_resampler.py`
- [ ] **Commit:** `feat: remediate timeseries specialization knots`

---

## Phase 9 — Lakehouse Base Class Consistency

- [ ] `pirn/domains/data/frames/lakehouse/lakehouse_table_source.py` — change base `Knot` → `Source`
- [ ] `pirn/domains/data/frames/lakehouse/lakehouse_table_sink.py` — change base `Knot` → `Sink`
- [ ] Update tests
- [ ] **Commit:** `feat: align LakehouseTableSource/Sink with Source/Sink base classes`

---

## Final Verification

- [ ] Run `uv run python scripts/audit_knots.py` — expect zero violations
- [ ] Run `uv run ruff check pirn/domains/data/`
- [ ] Run `uv run pyright pirn/domains/data/`
- [ ] Run `uv run pytest tests/unit/ -x -q`
