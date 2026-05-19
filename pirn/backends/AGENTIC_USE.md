`pirn.backends` provides pluggable implementations of the three storage protocols (`TapestryStore`, `RunHistory`, `DataStore`) and the cloud object store base — it does not execute pipelines or process domain data.

---

## Mental model

Every `Tapestry` holds three backend slots, each independently swappable:

| Slot | Protocol | Stores | Default |
|------|----------|--------|---------|
| `store` | `TapestryStore` | Knot registrations (the pipeline definition) | `InMemoryStore` |
| `history` | `RunHistory` | Run results and per-knot lineage records | `InMemoryHistory` |
| `data` | `DataStore` | Intermediate values keyed by content hash | `InMemoryDataStore` |

Pass backends to `Tapestry(store=..., history=..., data=...)`. Backends that are not passed default to their in-memory counterparts. The three slots are decoupled — you can persist lineage to SQLite while keeping values in memory.

`SubscribableStore` is a mixin implemented by `InMemoryStore`, `PostgresStore`, and `ValKeyStore`. It adds `subscribe()` for live notifications when knots are registered — required for `WithContinuation` and extensible runs.

---

## Source map

```
pirn/backends/
├── base/
│   ├── tapestry_store.py     TapestryStore        — interface: register, get, all, snapshot
│   ├── run_history.py        RunHistory           — interface: record_run, get_run, query_lineage_*
│   ├── data_store.py         DataStore            — interface: put, get, has, delete
│   ├── subscribable_store.py SubscribableStore    — mixin: subscribe() for live registration events
│   └── tapestry_snapshot.py  TapestrySnapshot     — frozen Pydantic model: ordered knot id list
├── in_memory/
│   ├── in_memory_store.py    InMemoryStore        — TapestryStore + SubscribableStore; default
│   ├── in_memory_history.py  InMemoryHistory      — RunHistory; default; not persistent
│   └── in_memory_data_store.py InMemoryDataStore  — DataStore; default; not persistent
├── sqlite/
│   ├── sqlite_store.py       SQLiteStore          — TapestryStore backed by SQLite
│   └── sqlite_history.py     SQLiteHistory        — RunHistory backed by SQLite; durable
├── postgres/
│   ├── postgres_store.py     PostgresStore        — TapestryStore + SubscribableStore; asyncpg
│   └── postgres_history.py   PostgresHistory      — RunHistory backed by Postgres; durable
├── valkey/
│   ├── valkey_store.py       ValKeyStore          — TapestryStore + SubscribableStore; Valkey/Redis
│   └── valkey_data_store.py  ValKeyDataStore      — DataStore backed by Valkey/Redis; pickle-serialised
├── duckdb.py                 DuckDBHistory        — RunHistory backed by DuckDB; analytical queries
├── s3.py                     S3DataStore          — DataStore backed by AWS S3; pickle-serialised
├── gcs.py                    GCSDataStore         — DataStore backed by Google Cloud Storage
├── azure.py                  AzureBlobDataStore   — DataStore backed by Azure Blob Storage
└── disk.py                   LocalDiskDataStore   — DataStore backed by local filesystem; pickle-serialised
```

---

## Canonical pattern

### Development — all in memory (default)

```python
from pirn import Tapestry, RunRequest

# No backends passed — all three slots use in-memory defaults.
with Tapestry() as t:
    ...

result = await t.run(RunRequest())
```

### Production — durable lineage, in-memory values

```python
from pirn import Tapestry, RunRequest
from pirn.backends.sqlite.sqlite_history import SQLiteHistory

history = SQLiteHistory(path="pirn.db")

with Tapestry(history=history) as t:
    ...

result = await t.run(RunRequest())
# result.lineage is now persisted across process restarts
```

### Querying lineage across runs

```python
records = await history.query_lineage_by_knot_id("my-knot-id")
for rec in records:
    print(rec.run_id, rec.outcome, rec.output_hash)
```

### Persisting intermediate values (S3)

```python
from pirn.backends.s3 import S3DataStore

data = S3DataStore(bucket="my-pirn-bucket", prefix="runs/")
with Tapestry(data=data) as t:
    ...
```

### Shared tapestry definition (Postgres — multi-process)

```python
from pirn.backends.postgres.postgres_store import PostgresStore
from pirn.backends.postgres.postgres_history import PostgresHistory

store   = PostgresStore(dsn="postgresql://user:pass@host/pirn")
history = PostgresHistory(dsn="postgresql://user:pass@host/pirn")

with Tapestry(store=store, history=history) as t:
    ...
```

---

## Anti-patterns

### Using cloud DataStores with untrusted infrastructure

`S3DataStore`, `GCSDataStore`, `AzureBlobDataStore`, and `LocalDiskDataStore` serialise values with `pickle`. Any store writable by an adversary can execute arbitrary code on deserialization. Only use these backends when the backing store is fully access-controlled.

### Assuming `InMemoryHistory` persists across runs

`InMemoryHistory` holds results in a dict for the lifetime of the process. Restarting the process loses all lineage. Use `SQLiteHistory`, `PostgresHistory`, or `DuckDBHistory` for durability.

### Using extensible runs with non-memory `TapestryStore`

`tapestry.run(extensible=True)` (required by `WithContinuation` and `LoopSubTapestry`) calls `get_current_store()` mid-run to register new knots. Only `InMemoryStore`, `PostgresStore`, and `ValKeyStore` (all `SubscribableStore` implementors) support this. `SQLiteStore` does not.

### Scrubbing `DataStore` values and expecting lineage to break

`DataStore` and `RunHistory` are decoupled by design. Deleting a value from the data store removes the payload but leaves the lineage hash record intact. This is intentional for GDPR-style scrubbing.

---

## Constraints and gotchas

- **`SQLiteHistory` runs migrations on first open.** The first `SQLiteHistory(path=...)` call creates the schema. Concurrent first-opens from multiple processes can race — initialise from a single process or use Postgres for multi-process deployments.
- **`DuckDBHistory` is optimised for analytical queries, not writes.** Use it for offline lineage analysis, not as the primary history backend of a high-throughput pipeline.
- **`ValKeyDataStore` and `LocalDiskDataStore` are pickle-based.** See anti-pattern above.
- **`PostgresStore` and `ValKeyStore` implement `SubscribableStore`.** If you need extensible runs in a distributed deployment, these are the only backends that support it.
- **Backend constructors are synchronous; connections are lazy.** `PostgresStore(dsn=...)` does not open a connection immediately. The first operation opens it. Call `await backend.close()` when done.
- **`DataStore.has()` is a cheap existence check** — use it before `get()` when a miss is a valid path, rather than catching `KeyError`.

---

## Quick reference

| Task | How |
|------|-----|
| Default (dev, no persistence) | `Tapestry()` — all in-memory |
| Durable lineage (single process) | `Tapestry(history=SQLiteHistory(path="pirn.db"))` |
| Durable lineage (multi-process) | `Tapestry(history=PostgresHistory(dsn=...))` |
| Analytical lineage queries | `DuckDBHistory(path="lineage.duckdb")` |
| Persist intermediate values to S3 | `Tapestry(data=S3DataStore(bucket=..., prefix=...))` |
| Persist intermediate values to GCS | `Tapestry(data=GCSDataStore(bucket=..., prefix=...))` |
| Persist intermediate values to Azure | `Tapestry(data=AzureBlobDataStore(container=..., prefix=...))` |
| Persist intermediate values to disk | `Tapestry(data=LocalDiskDataStore(root=Path("/data")))` |
| Shared tapestry definition (multi-process) | `Tapestry(store=PostgresStore(dsn=...))` |
| Shared tapestry + extensible runs | `Tapestry(store=PostgresStore(dsn=...), ...)` — `SubscribableStore` required |
| Query lineage by knot id | `await history.query_lineage_by_knot_id("my-id")` |
| Query lineage by output hash | `await history.query_lineage_by_output_hash("sha256:abc...")` |
| Check if a value is cached | `await data_store.has("sha256:abc...")` |
| Retrieve a cached value | `await data_store.get("sha256:abc...")` |
| Scrub a value (GDPR) | `await data_store.delete("sha256:abc...")` — lineage record is preserved |

---

*See also: [pirn AGENTIC_USE.md](../../AGENTIC_USE.md)*
