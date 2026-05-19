`pirn.domains.data.lakehouse` provides source and sink knots for Delta Lake, Apache Hudi, and Apache Iceberg table formats — it does not manage schema evolution or table maintenance; use the table format's own tooling (VACUUM, OPTIMIZE, compaction) for that.

---

## Mental model

A `LakehouseTable` is a config object that identifies a table in a specific open table format. Pass it to `LakehouseTableSource` to read or `LakehouseTableSink` to write. The `LakehouseTable` holds no live connection — it is a description of the table location and format, passed as a config constant.

All three formats support ACID writes, time-travel reads, and schema evolution — choose by ecosystem: Delta Lake for Databricks, Hudi for AWS/Spark streaming, Iceberg for multi-engine or Snowflake/BigQuery external table use.

---

## Source map

```
pirn/domains/data/lakehouse/
├── lakehouse_table.py         LakehouseTable         — config: format (delta/hudi/iceberg), path/uri, table_name
├── lakehouse_table_source.py  LakehouseTableSource   — read from a lakehouse table (full or time-travel)
├── lakehouse_table_sink.py    LakehouseTableSink     — write to a lakehouse table (append, overwrite, merge)
├── delta/
│   ├── delta_table.py         DeltaTable             — Delta Lake table wrapper (delta-rs)
│   └── delta_table_config.py  DeltaTableConfig       — path, storage_options, version (time-travel)
├── hudi/
│   └── (HudiTable, HudiTableConfig — same pattern)
└── iceberg/
    └── (IcebergTable, IcebergTableConfig — same pattern)
```

---

## Canonical pattern

### Read from a Delta Lake table

```python
from pirn.domains.data.lakehouse.lakehouse_table import LakehouseTable
from pirn.domains.data.lakehouse.lakehouse_table_source import LakehouseTableSource
from pirn import Tapestry, KnotConfig, RunRequest

table = LakehouseTable(format="delta", path="s3://my-bucket/tables/events")

with Tapestry() as t:
    rows = LakehouseTableSource(table=table, _config=KnotConfig(id="read"))
    ProcessKnot(data=rows, _config=KnotConfig(id="process"))

result = await t.run(RunRequest())
```

### Write with merge (upsert) to Delta Lake

```python
from pirn.domains.data.lakehouse.lakehouse_table_sink import LakehouseTableSink

with Tapestry() as t:
    rows = ProcessKnot(_config=KnotConfig(id="process"))
    LakehouseTableSink(
        data=rows,
        table=table,
        mode="merge",
        merge_key="event_id",
        _config=KnotConfig(id="write"),
    )
```

### Time-travel read (Delta Lake)

```python
from pirn.domains.data.lakehouse.delta.delta_table_config import DeltaTableConfig
from pirn.domains.data.lakehouse.delta.delta_table import DeltaTable

cfg   = DeltaTableConfig(path="s3://my-bucket/tables/events", version=42)
table = DeltaTable(config=cfg)
```

---

## Anti-patterns

**Mixing `LakehouseTableSink(mode="overwrite")` with concurrent writers** — overwrite mode replaces the entire table. With concurrent writers this causes data loss. Use `mode="append"` or `mode="merge"` for concurrent pipelines.

**Reading a Hudi table with `delta` format** — the format must match. `LakehouseTable(format="delta")` uses delta-rs; specifying the wrong format will fail silently or produce incorrect results.

---

## Constraints and gotchas

- **Each format requires its own extra:** `pirn[delta]`, `pirn[hudi]`, `pirn[iceberg]`.
- **`DeltaTableSink(mode="merge")` requires `merge_key` to identify the column(s) used for matching rows.** Without it, the merge cannot determine which rows to update.
- **Iceberg requires a catalog** (Hive Metastore, Glue, Nessie, REST) — the table URI alone is not sufficient. Pass `catalog=` to `IcebergTableConfig`.
- **Time-travel reads via `version=` or `timestamp=` are supported on Delta and Iceberg.** Hudi uses `as_of_instant` syntax — pass via `IcebergTableConfig`/`HudiTableConfig` options.

---

## Quick reference

| Task | How |
|------|-----|
| Read a Delta table | `LakehouseTableSource(table=LakehouseTable(format="delta", path=...))` |
| Append to a Delta table | `LakehouseTableSink(data=..., table=..., mode="append")` |
| Merge/upsert into Delta | `LakehouseTableSink(data=..., table=..., mode="merge", merge_key=...)` |
| Time-travel read (Delta) | `DeltaTable(config=DeltaTableConfig(path=..., version=N))` |
| Read an Iceberg table | `LakehouseTable(format="iceberg", ...)` |

---

*See also: [data AGENTIC_USE.md](../AGENTIC_USE.md)*
