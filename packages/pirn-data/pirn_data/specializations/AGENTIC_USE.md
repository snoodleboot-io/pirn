`pirn_data.specializations` provides pre-built data engineering patterns (medallion, SCD, incremental, data vault, and more) built on the data tier knots — it does not provide the frame/lazy execution engines; those come from `pirn_data.frames` and `pirn_data.lazy`.

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
from pirn_data.specializations.medallion.bronze_raw_ingest import BronzeRawIngest
from pirn_data.specializations.medallion.silver_clean_transform import SilverCleanTransform
from pirn_data.specializations.medallion.gold_aggregation import GoldAggregation
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

with Tapestry() as t:
    raw    = BronzeRawIngest(source=my_source_knot, _config=KnotConfig(id="bronze"))
    clean  = SilverCleanTransform(data=raw, rules=my_rules, _config=KnotConfig(id="silver"))
    agg    = GoldAggregation(data=clean, group_by=["region"], _config=KnotConfig(id="gold"))
    Sink(data=agg, _config=KnotConfig(id="sink"))
```

### SCD Type 2 — track history for a dimension table

```python
from pirn_data.specializations.scd.scd_type_2 import ScdType2

with Tapestry() as t:
    # Rows from an upstream knot, one value per column_names entry ...
    incoming = SourceKnot(_config=KnotConfig(id="source"))
    ScdType2(
        rows=incoming,
        target_pool=my_pool,
        target_table="dim_customer",
        primary_keys=("customer_id",),
        column_names=("customer_id", "region", "tier"),
        _config=KnotConfig(id="scd2"),
    )

with Tapestry() as t:
    # ... or a query ScdType2 runs itself. Supply one or the other, never both.
    ScdType2(
        source_pool=my_pool,
        source_query="SELECT customer_id, region, tier FROM stg_customer",
        target_pool=my_pool,
        target_table="dim_customer",
        primary_keys=("customer_id",),
        column_names=("customer_id", "region", "tier"),
        _config=KnotConfig(id="scd2"),
    )
```

### Incremental merge-upsert (SCD Type 1)

```python
from pirn_data.specializations.scd.scd_type_1 import ScdType1

with Tapestry() as t:
    new_rows = SourceKnot(_config=KnotConfig(id="source"))
    ScdType1(
        rows=new_rows,
        target_pool=my_pool,
        target_table="events",
        primary_keys=("event_id",),
        column_names=("event_id", "payload"),
        _config=KnotConfig(id="upsert"),
    )
```

---

## Anti-patterns

**Using `ScdType2` where you meant `ScdType7`** — `ScdType2` versions rows by natural key and never allocates a surrogate key, so the target table must not declare the natural key as its primary key (several versions of a key coexist). `ScdType7` is the one that allocates a surrogate key per version.

**Skipping `BronzeRawIngest` and writing directly to Silver** — bronze is the immutable landing zone. Bypass it and you lose the audit trail and the ability to reprocess from raw.

---

## Constraints and gotchas

- **SCD Types 3–7 are single-table implementations.** They are less common and have specific schema requirements — read each module's docstring for the expected table structure.
- **The SCD merges use only `SELECT`, `INSERT`, `UPDATE` and `?` placeholders** — no `MERGE` and no `INSERT ... ON CONFLICT` — so they run on every pool, not just the engines that have a vendor upsert.
- **Data Vault loaders assume a hash-key convention** — hub and satellite natural keys are SHA-256 hashed to produce the `HK_` (hub key) column. Ensure hash salting is consistent across loads.

---

## Quick reference

| Pattern | Entry point |
|---------|------------|
| Raw ingest (bronze) | `BronzeRawIngest` |
| Clean + validate (silver) | `SilverCleanTransform` |
| Aggregate (gold) | `GoldAggregation` |
| SCD Type 1 (overwrite) | `ScdType1` |
| SCD Type 2 (history) | `ScdType2` |
| SCD Type 7 (surrogate-keyed history) | `ScdType7` |
| Snapshot append | `SnapshotTableAppender` |
| Data Vault hub load | `DataVaultHubLoader` |
| Data Vault satellite load | `DataVaultSatelliteLoader` |

---

*See also: [data AGENTIC_USE.md](../AGENTIC_USE.md)*
