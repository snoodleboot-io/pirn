`pirn.domains.data.specializations` provides pre-built data engineering patterns (medallion, SCD, incremental, data vault, and more) built on the data tier knots — it does not provide the frame/lazy execution engines; those come from `pirn.domains.data.frames` and `pirn.domains.data.lazy`.

---

## Mental model

Specializations are composable pipeline patterns over the data tier. Each sub-package targets a well-known data engineering concept and provides the knots that implement it. All knots accept `DataBatch` inputs (the data tier's typed record container) and emit `DataBatch` outputs. Wire them after a Tier 1 source knot and before a sink.

Choose a sub-package by the data management pattern you need, not the underlying technology — the same SCD Type 2 knot works whether the backing store is Postgres, DuckDB, or Delta Lake.

---

## Sub-package index

| Sub-package | Pattern | Contents |
|-------------|---------|---------|
| `medallion/` | Bronze → Silver → Gold pipeline stages | Raw ingest, clean transform, aggregation |
| `scd/` | Slowly changing dimensions (Types 1–7) with CDC support | SCD merge knots, CDC decoder |
| `incremental/` | Incremental load patterns | Merge-upsert, snapshot append, partitioned overwrite, dbt-style snapshot |
| `data_vault/` | Data Vault 2.0 loaders | Hub, Link, Satellite loaders; PIT and Bridge table builders |
| `quality/` | Data quality checks and assertions | — |
| `feature_engineering/` | Feature derivation over `DataBatch` | — |
| `analytics_engineering/` | dbt-style transform patterns | — |
| `dimensional/` | Dimensional modelling (fact/dim) | — |
| `deduplication/` | Record deduplication | — |
| `ingestion/` | Source ingestion helpers | — |
| `schema_migration/` | Schema evolution helpers | — |
| `timeseries/` | Time-series specific transforms | — |

---

## Canonical pattern

### Medallion pipeline — raw to silver

```python
from pirn.domains.data.specializations.medallion.bronze_raw_ingest import BronzeRawIngest
from pirn.domains.data.specializations.medallion.silver_clean_transform import SilverCleanTransform
from pirn.domains.data.specializations.medallion.gold_aggregation import GoldAggregation
from pirn import Tapestry, KnotConfig, RunRequest

with Tapestry() as t:
    raw    = BronzeRawIngest(source=my_source_knot, _config=KnotConfig(id="bronze"))
    clean  = SilverCleanTransform(data=raw, rules=my_rules, _config=KnotConfig(id="silver"))
    agg    = GoldAggregation(data=clean, group_by=["region"], _config=KnotConfig(id="gold"))
    Sink(data=agg, _config=KnotConfig(id="sink"))
```

### SCD Type 2 — track history for a dimension table

```python
from pirn.domains.data.specializations.scd.scd_type_2 import ScdType2
from pirn.domains.data.specializations.scd.scd_type_2_merge_knot import ScdType2MergeKnot

with Tapestry() as t:
    incoming = SourceKnot(_config=KnotConfig(id="source"))
    merged   = ScdType2MergeKnot(
        incoming=incoming,
        pool=my_pool,
        table="dim_customer",
        natural_key="customer_id",
        _config=KnotConfig(id="scd2"),
    )
```

### Incremental merge-upsert

```python
from pirn.domains.data.specializations.incremental.merge_upsert import MergeUpsert

with Tapestry() as t:
    new_rows = SourceKnot(_config=KnotConfig(id="source"))
    MergeUpsert(
        data=new_rows,
        pool=my_pool,
        table="events",
        key_columns=["event_id"],
        _config=KnotConfig(id="upsert"),
    )
```

---

## Anti-patterns

**Using `ScdType2MergeKnot` without a surrogate key column** — SCD Type 2 generates surrogate keys on insert. If the target table already has a primary key scheme that conflicts, the merge will produce duplicate rows.

**Skipping `BronzeRawIngest` and writing directly to Silver** — bronze is the immutable landing zone. Bypass it and you lose the audit trail and the ability to reprocess from raw.

---

## Constraints and gotchas

- **SCD Types 3–7 are single-table implementations.** They are less common and have specific schema requirements — read each module's docstring for the expected table structure.
- **`MergeUpsert` requires the pool's database to support `MERGE` or `INSERT ... ON CONFLICT`.** Verified on Postgres, DuckDB, Snowflake, BigQuery. Not supported on all databases.
- **Data Vault loaders assume a hash-key convention** — hub and satellite natural keys are SHA-256 hashed to produce the `HK_` (hub key) column. Ensure hash salting is consistent across loads.

---

## Quick reference

| Pattern | Entry point |
|---------|------------|
| Raw ingest (bronze) | `BronzeRawIngest` |
| Clean + validate (silver) | `SilverCleanTransform` |
| Aggregate (gold) | `GoldAggregation` |
| SCD Type 1 (overwrite) | `ScdType1MergeKnot` |
| SCD Type 2 (history) | `ScdType2MergeKnot` |
| Merge-upsert | `MergeUpsert` |
| Snapshot append | `SnapshotTableAppender` |
| Data Vault hub load | `DataVaultHubLoader` |
| Data Vault satellite load | `DataVaultSatelliteLoader` |

---

*See also: [data AGENTIC_USE.md](../AGENTIC_USE.md)*
