# AGENTIC_USE — pirn_data

Provides a tiered, engine-agnostic layer for reading, transforming, and writing structured data — it does NOT include API connectors, message-queue consumers, or ML training loops (those are separate domains).

---

## Mental model

pirn is the **orchestrator**; the engines do the work. The data domain is stratified into tiers, each independently opt-in:

| Tier | Label | Engines | When to use |
|------|-------|---------|-------------|
| **1** | Dict / DataBatch | Pure Python | Always available. Use for < ~100 k rows, glue logic, or environments where no heavy deps are allowed. Every record is a `dict`; the exchange currency is `DataBatch`. |
| **2** | Native frames (CPU) | **Polars** (preferred), DuckDB, pandas+PyArrow, DataFusion | Fits comfortably in RAM. Need fast vectorised ops, joins, window functions, pivots. Polars is the default; reach for DuckDB when SQL is more natural or when you need concurrent read-only queries. |
| **2-GPU** | Native frames (GPU) | cuDF | CUDA cluster only. Drop-in Polars-compatible when `cudf-cu12` is installed. |
| **2.5** | Out-of-core | Modin | Data exceeds RAM, single machine. Pandas-compatible API chunked on disk. |
| **3** | Lazy / push-down | **Ibis** (preferred), Spark, Dask, Ray Data | Data doesn't fit on one machine, or lives in a warehouse already. Ibis first — it targets many backends without a Spark cluster. Spark/Dask/Ray when distributed compute is required. |
| **3-stream** | Streaming dataflow | Pathway, Bytewax | Continuous / low-latency event streams. Requires Python < 3.14 until upstream catches up. |
| **4** | Specialised | Lance (vector), Eland (Elasticsearch) | Domain-specific columnar layouts; not general-purpose. |

**Tier-1 (`DataBatch`) is always installed with `pirn[data]`.** Tiers 2–4 are independent extras that do not pull each other in.

---

## Install

```bash
pip install pirn[data]          # Tier 1 only — DataBatch, sources, sinks, transforms (no heavy deps)
pip install pirn[all-frames]    # Tier 2 single-machine engines (Polars, DuckDB, pandas, PyArrow, DataFusion)
pip install pirn[all-lazy]      # Tier 3 push-down engines (Ibis, Spark, Dask, Ray Data)
```

Specialised extras (one at a time as needed):

```bash
pip install pirn[polars]        # Polars only
pip install pirn[delta]         # Delta Lake lakehouse adapter
pip install pirn[iceberg]       # Apache Iceberg adapter
pip install pirn[health]        # DICOM, HL7, FHIR, NIfTI, EDF, BIDS, etc.
pip install pirn[genomics]      # FASTA, FASTQ, VCF, BAM, CRAM, SAM
pip install pirn[oilgas]        # SEG-Y, DLIS, LAS, WITSML
```

---

## Source map

```
pirn_data/
├── data_batch.py               # Tier-1 exchange type: immutable tuple of dicts
├── data_schema.py              # Optional schema metadata attached to DataBatch
├── data_profile.py             # Statistical profile of a DataBatch
├── quality/                    # Quality checks and reports
│   ├── quality_check.py
│   └── quality_report.py
├── sources/
│   ├── file_source.py          # Single-file source (ObjectStore + FileFormat)
│   └── directory_source.py     # Prefix glob → one or many DataBatches
├── sinks/
│   └── file_sink.py            # Encode + write DataBatch to ObjectStore
├── transforms/                 # Tier-1 transforms (pure Python, no extras)
│   ├── filter.py               # Row predicate (Python callable)
│   ├── rename.py               # Column rename map
│   ├── cast.py                 # Type coercion
│   ├── normalize.py            # String cleanup rules
│   ├── aggregate.py            # Group-by + aggregations
│   └── deduplicate.py          # Row deduplication
├── frames/                     # Tier-2 engine-specific knots
│   ├── polars/                 # PolarsFilter, PolarsJoin, PolarsAggregate, etc.
│   │   └── bridges/            # DataBatch ↔ PolarsDataBatch conversions
│   ├── duckdb/                 # DuckDB equivalents
│   ├── pandas/
│   ├── pyarrow/
│   └── datafusion/
├── lazy/                       # Tier-3 lazy/push-down knots
│   ├── ibis/
│   ├── spark/
│   ├── dask/
│   └── ray/
├── lakehouse/                  # Lakehouse table adapters
│   ├── delta/                  # DeltaTable (full CRUD + merge + time-travel)
│   ├── iceberg/                # IcebergTable (read/write/time-travel; merge not yet available in pyiceberg)
│   └── hudi/                   # HudiTable (read-only; writes require Spark writer)
├── specializations/            # Pre-wired high-level patterns  ← specializations
│   ├── ingestion/              # AppendOnlyIngest, FullRefreshExtract, WatermarkIncrementalExtract  ← specializations
│   ├── medallion/              # BronzeRawIngest, SilverCleanTransform, GoldAggregation  ← specializations
│   ├── scd/                   # ScdType1/2/3/4/5/6/7, CdcDebezium, DebeziumSource  ← specializations
│   ├── dimensional/            # DateDimGenerator, DimTableLoad, FactTableLoad, BridgeTableBuilder  ← specializations
│   ├── data_vault/             # DataVaultHubLoader, DataVaultLinkLoader, DataVaultSatelliteLoader, DataVaultPITTableBuilder, DataVaultBridgeTableBuilder  ← specializations
│   ├── incremental/            # SnapshotTableAppender, DbtStyleSnapshot, MergeUpsert, DeleteSafeSync, PartitionedOverwrite  ← specializations
│   ├── quality/                # RowCountAnomalyDetector, NullRateMonitor, SchemaEvolutionDetector, FreshnessCheck, ReferentialIntegrityCheck, ReconciliationDiff, StatisticalProfiler  ← specializations
│   ├── deduplication/          # ExactDeduplicator, WindowedDeduplicator, FuzzyDeduplicator, ProbabilisticLinker  ← specializations
│   ├── timeseries/             # TimeSeriesResampler, RollingWindowAggregator, SessionizationKnot, FunnelAnalysisKnot, CohortAggregator, LateArrivingEventHandler  ← specializations
│   ├── feature_engineering/    # DerivedColumnCalculator, ColumnHasher, BinningKnot, StringNormalizer, DatePartExtractor, LookupEnricher, GeoEnricher, TextTokenCounter  ← specializations
│   ├── analytics_engineering/  # StagingModelKnot, IntermediateModelKnot, MartModelKnot, RefreshMaterializedView, MetricLayerAggregator, ExposureLineageTag  ← specializations
│   └── schema_migration/       # BackfillRunner, SchemaVersionMigrator, ColumnLineageTracker  ← specializations
└── specialized/                # Tier-4 specialised adapters (Lance, Eland)
```

File formats and object stores live under `pirn/domains/connectors/`, not here.

---

## Tier selection guide

| Data size | Latency need | Infrastructure | Recommended tier |
|-----------|-------------|----------------|-----------------|
| < 100 k rows | Any | Any | **Tier 1** — zero deps, fast enough |
| Fits in RAM (up to ~10 GB) | Batch | Single machine | **Tier 2 Polars** |
| Fits in RAM, SQL-heavy | Batch | Single machine | **Tier 2 DuckDB** |
| Exceeds RAM, single machine | Batch | Single machine | **Tier 2.5 Modin** |
| Warehouse-scale, existing backend | Batch | Any (warehouse/cluster) | **Tier 3 Ibis** |
| Distributed compute required | Batch | Spark / Dask / Ray cluster | **Tier 3 Spark/Dask/Ray** |
| Continuous / event-driven | Sub-second | Stream processor | **Tier 3-stream** |
| Vector similarity search | Any | Any | **Tier 4 Lance** |

---

## Canonical patterns

### Tier-1 dict batch pipeline

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.sources.file_source import FileSource
from pirn_data.transforms.filter import Filter
from pirn_data.transforms.aggregate import Aggregate
from pirn_data.transforms.aggregate_spec import AggregateSpec
from pirn_data.sinks.file_sink import FileSink
from pirn.connectors.file_formats.csv_format import CsvFormat
from pirn.connectors.file_formats.parquet_format import ParquetFormat
from pirn.connectors.object_stores.local_object_store import LocalObjectStore

with Tapestry() as t:
    store = LocalObjectStore(root="/data")
    source = FileSource(
        store=store,
        format=CsvFormat(),
        key="input/sales.csv",
        _config=KnotConfig(id="source"),
    )
    active = Filter(
        batch=source,
        predicate=lambda row: row["status"] == "active",
        _config=KnotConfig(id="active_only"),
    )
    summary = Aggregate(
        batch=active,
        by=["region"],
        aggs={"revenue": AggregateSpec(op="sum", column="revenue")},
        _config=KnotConfig(id="by_region"),
    )
    FileSink(
        batch=summary,
        store=store,
        format=ParquetFormat(compression="zstd"),
        key="output/region_revenue.parquet",
        _config=KnotConfig(id="sink"),
    )

result = await t.run(RunRequest(parameters={}))
```

### Tier-2 Polars pipeline

```python
import polars as pl
from pirn_data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn_data.frames.polars.polars_filter import PolarsFilter
from pirn_data.frames.polars.polars_join import PolarsJoin
from pirn_data.frames.polars.polars_aggregate import PolarsAggregate
from pirn_data.frames.polars.bridges.data_batch_to_polars import DataBatchToPolars
from pirn_data.frames.polars.bridges.polars_to_data_batch import PolarsToDataBatch

# Promote a Tier-1 source to a Polars frame
polars_batch = DataBatchToPolars(
    batch=source,
    _config=KnotConfig(id="to_polars"),
)
filtered = PolarsFilter(
    batch=polars_batch,
    expression=pl.col("region") == "EU",
    _config=KnotConfig(id="eu_only"),
)
joined = PolarsJoin(
    left=filtered,
    right=ref_batch,
    on="region",
    how="left",
    _config=KnotConfig(id="join_ref"),
)
# Demote back to Tier-1 DataBatch if downstream knots expect it
result_batch = PolarsToDataBatch(
    batch=joined,
    _config=KnotConfig(id="to_data_batch"),
)
```

---

## Anti-patterns

### Reaching for Tier 3 when data fits in memory

Ibis/Spark add serialisation overhead and cluster setup cost. If the dataset fits in RAM, use Tier-2 Polars. Reserve Tier-3 for warehouse-resident data or genuinely distributed workloads.

### Mixing tier knots without conversion bridges

Passing a `PolarsDataBatch` directly into a Tier-1 `Filter` (or vice versa) will fail at runtime because the knots expect different input types. Always interpose the bridge knots:

- `DataBatchToPolars` — `DataBatch` → `PolarsDataBatch`
- `PolarsToDataBatch` — `PolarsDataBatch` → `DataBatch`

Equivalent bridges exist in `frames/duckdb/bridges/`.

### Using Tier-1 `Aggregate` for joins

Tier-1 has no `Join` knot — a Python-level hash-join of two `tuple[dict]` lists would be O(n·m) without indexes. If you need joins, promote to Tier 2 first with a bridge knot, then use `PolarsJoin` or `DuckDbJoin`.

### Calling `IcebergTable.merge()` in production

As of mid-2026, `pyiceberg`'s Python writer does not implement merge. The method raises `NotImplementedError`. Use the Java/Scala Iceberg writer for production upserts.

### Writing to a Hudi table from Python

`HudiTable` is read-only. All write methods raise `NotImplementedError`. Writes require the `hudi-spark-bundle` Spark writer.

### Instantiating format objects inside `process()`

`FileFormat` objects are stateless but they import their vendor library at construction time. Build them once at pipeline-wiring time, not inside knot `process()` methods.

---

## Constraints and gotchas

- **`DataBatch.rows` is a `tuple`** (immutable). Never mutate it. Produce a new batch with `batch.with_rows(new_rows)` — this preserves `schema` and `source_uri`.
- **`DirectorySource` with `concatenate=True` loses per-file lineage.** The `source_uri` collapses to `{store}://{prefix}*`. Use `concatenate=False` when provenance matters.
- **`Aggregate` skips `None` values.** Empty groups yield `None` for mean/min/max/first/last and `0` for count/count_distinct.
- **Tier-3-stream requires Python < 3.14** until Pathway and Bytewax catch up to the new Python release.
- **`pirn[hudi]` is a no-op marker extra** — there is no stable vendor SDK on PyPI. The read path relies only on `pyarrow` (included with `pirn[data]`).
- **`CompressedFileFormat` codec availability varies.** `gzip` and `bzip2` use stdlib and are always available. `zstd`, `snappy`, and `lz4` each require their own extra.
- **`ArchiveFileFormat` is always non-streaming** — the full archive must be buffered. Do not use it for large files where incremental streaming matters.
- **`FileSink.process()` returns the destination `key` string**, not a `DataBatch`. Downstream knots that expect a `DataBatch` must not follow a `FileSink` directly.
- **Lakehouse vendor SDKs load lazily.** Import errors for missing extras are raised on first use, not at module import time.

---

## Quick reference

| Task | Tier | Knot / Class |
|------|------|-------------|
| Read a single file | 1 | `FileSource` |
| Read all files under a prefix | 1 | `DirectorySource` |
| Write a file | 1 | `FileSink` |
| Filter rows (Python callable) | 1 | `Filter` |
| Rename columns | 1 | `Rename` |
| Type coercion | 1 | `Cast` |
| String normalisation | 1 | `Normalize` |
| Group-by aggregation | 1 | `Aggregate` |
| Deduplication | 1 | `Deduplicate` |
| Vectorised filter (Polars expr) | 2 | `PolarsFilter` |
| Join two frames | 2 | `PolarsJoin` / `DuckDbJoin` |
| Window functions | 2 | `PolarsWindowCalc` |
| Pivot / unpivot | 2 | `PolarsPivot` / `PolarsUnpivot` |
| DataBatch → Polars | bridge | `DataBatchToPolars` |
| Polars → DataBatch | bridge | `PolarsToDataBatch` |
| Delta Lake read/write/merge | lakehouse | `DeltaTable` + `LakehouseTableSource` |
| Iceberg read/write | lakehouse | `IcebergTable` |
| Hudi read (only) | lakehouse | `HudiTable` |
| Bronze raw ingest | specialisation | `BronzeRawIngest` |
| Silver clean transform | specialisation | `SilverCleanTransform` |
| Gold aggregation | specialisation | `GoldAggregation` |
| Incremental watermark ingest | specialisation | `WatermarkIncrementalExtract` |
| SCD Type 2 history | specialisation | `ScdType2` |
| SCD Type 3 previous value | specialisation | `ScdType3PreviousValue` |
| SCD Type 4 mini-dimension | specialisation | `ScdType4MiniDimension` |
| SCD Type 6 hybrid (1+2+3) | specialisation | `ScdType6Hybrid` |
| Debezium CDC apply | specialisation | `CdcDebezium` |
| Date dimension generate | specialisation | `DateDimGenerator` |
| Dimension table load | specialisation | `DimTableLoad` |
| Fact table load | specialisation | `FactTableLoad` |
| Data Vault hub load | specialisation | `DataVaultHubLoader` |
| Data Vault satellite load | specialisation | `DataVaultSatelliteLoader` |
| Data Vault PIT table | specialisation | `DataVaultPITTableBuilder` |
| Snapshot append | specialisation | `SnapshotTableAppender` |
| dbt-style snapshot | specialisation | `DbtStyleSnapshot` |
| Merge upsert | specialisation | `MergeUpsert` |
| Row count anomaly | specialisation | `RowCountAnomalyDetector` |
| Null rate monitor | specialisation | `NullRateMonitor` |
| Referential integrity check | specialisation | `ReferentialIntegrityCheck` |
| Reconciliation diff | specialisation | `ReconciliationDiff` |
| Exact deduplication | specialisation | `ExactDeduplicator` |
| Fuzzy deduplication | specialisation | `FuzzyDeduplicator` |
| Time series resample | specialisation | `TimeSeriesResampler` |
| Rolling window aggregation | specialisation | `RollingWindowAggregator` |
| Sessionization | specialisation | `SessionizationKnot` |
| Derived column calculation | specialisation | `DerivedColumnCalculator` |
| Binning / bucketing | specialisation | `BinningKnot` |
| Lookup enrichment | specialisation | `LookupEnricher` |
| dbt staging model | specialisation | `StagingModelKnot` |
| dbt mart model | specialisation | `MartModelKnot` |
| Metric layer aggregation | specialisation | `MetricLayerAggregator` |
| Schema version migration | specialisation | `SchemaVersionMigrator` |
| Backfill runner | specialisation | `BackfillRunner` |
| Column lineage tracking | specialisation | `ColumnLineageTracker` |
| Compressed format | wrapper | `CompressedFileFormat(inner, codec=...)` |
| Multi-file archive | wrapper | `ArchiveFileFormat(inner, archive_type=...)` |

---

*See also: [pirn AGENTIC_USE.md](../../AGENTIC_USE.md)*
