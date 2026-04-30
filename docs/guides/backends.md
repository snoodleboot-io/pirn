# Backends

pirn splits persistence into three independent roles. Pick the right implementation for each role and combine them freely.

| Role | Interface | Question it answers |
|------|-----------|---------------------|
| `TapestryStore` | `pirn.backends.TapestryStore` | Where does the tapestry *definition* live? |
| `RunHistory` | `pirn.backends.RunHistory` | Where are lineage records and run summaries persisted? |
| `DataStore` | `pirn.backends.DataStore` | Where do intermediate values live between knots? |

---

## Capability matrix

| Backend | TapestryStore | RunHistory | DataStore | Subscribable | Notes |
|---------|:---:|:---:|:---:|:---:|-------|
| `InMemoryStore / InMemoryHistory / InMemoryDataStore` | Y | Y | Y | Y | Default. Single-process; lost on exit. Thread-safe via locks. |
| `SQLiteStore / SQLiteHistory` | Y | Y | — | N | Single-host durable. WAL mode recommended. |
| `PostgresStore / PostgresHistory` | Y | Y | — | Planned | OLTP. Async via `asyncpg`. Connection pooling required. |
| `DuckDBHistory` | — | Y | — | N | OLAP queries on lineage. Best as a read-path target. |
| `LocalDiskDataStore` | — | — | Y | N | Content-addressed files per value; survives restarts. |
| `S3DataStore` | — | — | Y | N | Distributed object storage. Requires `pirn[s3]`. |
| `ValkeyStore / ValkeyDataStore` | Y | — | Y | Planned | Low-latency. Optional TTL on data values. Requires `pirn[valkey]`. |

---

## TapestryStore

### InMemoryStore (default)

```python
from pirn import Tapestry
t = Tapestry()  # InMemoryStore is the default
```

No configuration. All knots are lost when the process exits. Suitable for tests, notebooks, and pipelines where the tapestry is reconstructed from code on each start.

### SQLiteStore

```python
from pirn.backends.sqlite import SQLiteStore

t = Tapestry(store=SQLiteStore("pirn.db"))
```

Requires `pip install pirn[sqlite]`. Uses WAL journal mode by default. Single-writer model — concurrent writers must serialize through SQLite's locking. Fine for single-process deployments.

### PostgresStore

```python
from pirn.backends.postgres import PostgresStore

store = PostgresStore(dsn="postgresql://user:pass@host/db")
t = Tapestry(store=store)
```

Requires `pip install pirn[postgres]`. Connection pooled via `asyncpg`. Schema is versioned with migrations applied automatically on first connection.

### ValkeyStore

```python
from pirn.backends.valkey import ValkeyStore

store = ValkeyStore(url="redis://localhost:6379", ttl=3600)
t = Tapestry(store=store)
```

Requires `pip install pirn[valkey]`. Uses `valkey-glide`. Optional TTL for ephemeral tapestries — useful in serverless deployments.

---

## RunHistory

### InMemoryHistory (default)

Lost on process exit. Suitable for tests and one-shot runs where you read the `RunResult` immediately.

### SQLiteHistory

```python
from pirn.backends.sqlite import SQLiteHistory

t = Tapestry(history=SQLiteHistory("pirn.db"))
```

Can share the same database file as `SQLiteStore`. Sustains ~5,000 lineage writes/sec in WAL mode. Switch to `PostgresHistory` for multi-process deployments.

### DuckDBHistory

```python
from pirn.backends.duckdb import DuckDBHistory

history = DuckDBHistory("lineage.duckdb")
```

Requires `pip install pirn[duckdb]`. Column-oriented — scanning millions of lineage rows for `P99(duration_ms) GROUP BY knot_id` is orders of magnitude faster than SQLite for the same query. Best used as a read path (write to Postgres, sync to DuckDB for analytics).

### PostgresHistory

```python
from pirn.backends.postgres import PostgresHistory

history = PostgresHistory(dsn="postgresql://...")
t = Tapestry(history=history)
```

Requires `pip install pirn[postgres]`. Multi-host writes, transactional, replication-friendly. Schema-versioned.

---

## DataStore

### InMemoryDataStore (default)

No eviction. Suitable for short-lived pipelines and tests.

### LocalDiskDataStore

```python
from pirn.backends.disk import LocalDiskDataStore

data = LocalDiskDataStore("/var/pirn/data")
t = Tapestry(data_store=data)
```

One file per value, named by content hash. Survives process restarts. Supports `scrub()` for GDPR-style value erasure (the lineage hash reference remains intact).

!!! warning "Pickle serialisation"
    `LocalDiskDataStore` uses pickle. Only use it when the backing directory is not writable by adversaries.

### S3DataStore

```python
from pirn.backends.s3 import S3DataStore

data = S3DataStore(bucket="pirn-data", prefix="runs/", region="us-east-1")
t = Tapestry(data_store=data)
```

Requires `pip install pirn[s3]`. Uses `aiobotocore`. Suitable for large intermediate values and multi-worker deployments. Supports multipart upload.

!!! warning "Pickle serialisation"
    `S3DataStore` uses pickle. Only use it when the S3 bucket is not writable by adversaries or untrusted pipelines.

### ValkeyDataStore

```python
from pirn.backends.valkey import ValkeyDataStore

data = ValkeyDataStore(url="redis://localhost:6379", ttl_seconds=3600)
t = Tapestry(data_store=data)
```

Requires `pip install pirn[valkey]`. Sub-millisecond get/put. TTL causes values to auto-expire — useful for streaming pipelines where data has a natural expiry.

!!! warning "Pickle serialisation"
    `ValkeyDataStore` uses pickle. Only use it when the ValKey instance is not writable by adversaries.

---

## Decision guide

### Local development

No infrastructure, no persistence needed between runs:

```python
t = Tapestry()  # all defaults
```

### Single-host durable

One machine, survives restarts, no external services:

```python
from pirn import Tapestry
from pirn.backends.sqlite import SQLiteStore, SQLiteHistory
from pirn.backends.disk import LocalDiskDataStore

t = Tapestry(
    store=SQLiteStore("pirn.db"),
    history=SQLiteHistory("pirn.db"),
    data_store=LocalDiskDataStore("./pirn-data"),
)
```

Good for: cron pipelines, ETL jobs, solo developers, CI runners. Avoid for write-heavy multi-process workloads — SQLite serialises writers.

### Single-host with analytics

Add DuckDB for fast lineage queries:

```python
from pirn.backends.sqlite import SQLiteStore
from pirn.backends.duckdb import DuckDBHistory
from pirn.backends.disk import LocalDiskDataStore

t = Tapestry(
    store=SQLiteStore("pirn.db"),
    history=DuckDBHistory("lineage.duckdb"),
    data_store=LocalDiskDataStore("./pirn-data"),
)
```

### Distributed — high-throughput

Multiple hosts, durable lineage, large values:

```python
from pirn.backends.postgres import PostgresStore, PostgresHistory
from pirn.backends.s3 import S3DataStore

t = Tapestry(
    store=PostgresStore(dsn="postgresql://..."),
    history=PostgresHistory(dsn="postgresql://..."),
    data_store=S3DataStore(bucket="pirn-data", prefix="runs/"),
)
```

### Serverless / short TTL

ValKey for ephemeral values, Postgres for durable lineage:

```python
from pirn.backends.postgres import PostgresHistory
from pirn.backends.valkey import ValkeyStore, ValkeyDataStore

t = Tapestry(
    store=ValkeyStore(url="redis://...", ttl=300),
    history=PostgresHistory(dsn="postgresql://..."),
    data_store=ValkeyDataStore(url="redis://...", ttl_seconds=3600),
)
```

### Quick reference

| Deployment | Store | History | DataStore |
|------------|-------|---------|-----------|
| Local dev | `InMemory` | `InMemory` | `InMemory` |
| Single-host durable | `SQLite` | `SQLite` | `LocalDisk` |
| Single-host analytics | `SQLite` | `DuckDB` | `LocalDisk` |
| Multi-host | `Postgres` | `Postgres` | `S3` |
| Multi-host + OLAP | `Postgres` | `Postgres` + DuckDB reader | `S3` |
| Serverless / short TTL | `ValKey` | `Postgres` | `ValKey` |

---

## Subscribable stores

For mid-run extension (knots registered while a run is in progress), the store must implement `SubscribableStore`. Only `InMemoryStore` supports this in Phase 3. Pass `extensible=True` to `tapestry.run()`:

```python
result = await tapestry.run(request, extensible=True)
```

**See also:** [Deployment Sizing](deployment.md), [API — Backends](../api/backends.md)
