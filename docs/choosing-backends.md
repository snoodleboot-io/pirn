# Choosing backends

pirn splits persistence into three independent roles. Pick the right
implementation for each one and combine freely.

| Role | Interface | Question it answers |
|------|-----------|---------------------|
| **TapestryStore** | `pirn.backends.TapestryStore` | Where does the tapestry *definition* live? |
| **RunHistory** | `pirn.backends.RunHistory` | Where are lineage records and run summaries persisted? |
| **DataStore** | `pirn.backends.DataStore` | Where do intermediate values live between knots? |

---

## Available implementations

### TapestryStore

| Class | Import | Durable | Notes |
|-------|--------|---------|-------|
| `InMemoryStore` | `pirn.backends.in_memory` | No | Default. Gone when the process exits. |
| `SQLiteStore` | `pirn.backends.sqlite` | Yes | Single file, zero infra. WAL mode enabled. |
| `PostgresStore` | `pirn.backends.postgres` | Yes | Schema-versioned, connection-pooled. |
| `ValKeyStore` | `pirn.backends.valkey` | Yes | Optional TTL; use for distributed short-lived tapestries. |

### RunHistory

| Class | Import | Durable | Best for |
|-------|--------|---------|----------|
| `InMemoryHistory` | `pirn.backends.in_memory` | No | Tests, ephemeral pipelines. |
| `SQLiteHistory` | `pirn.backends.sqlite` | Yes | Single-host, < 50k runs/day. |
| `DuckDBHistory` | `pirn.backends.duckdb` | Yes | OLAP queries over millions of lineage records. |
| `PostgresHistory` | `pirn.backends.postgres` | Yes | Multi-host, transactional writes, replication. |

### DataStore

| Class | Import | Notes |
|-------|--------|-------|
| `InMemoryDataStore` | `pirn.backends.in_memory` | Default. No eviction. |
| `LocalDiskDataStore` | `pirn.backends.disk` | Content-addressed files; survives restarts. |
| `S3DataStore` | `pirn.backends.s3` | Large objects; needs `pirn[s3]`. |
| `ValKeyDataStore` | `pirn.backends.valkey` | Fast; optional TTL; needs `pirn[valkey]`. |

---

## Decision matrix

### Local development

No infrastructure, no persistence needed between runs.

```python
from pirn import Tapestry

t = Tapestry()           # InMemoryStore + InMemoryHistory + InMemoryDataStore
```

No imports required. This is the default.

---

### Single-host durable

One machine, survives restarts, no external services.

```python
from pirn import Tapestry
from pirn.backends.sqlite import SQLiteHistory, SQLiteStore
from pirn.backends.disk import LocalDiskDataStore

t = Tapestry(
    store=SQLiteStore("pirn.db"),
    history=SQLiteHistory("pirn.db"),
    data=LocalDiskDataStore("./pirn-data"),
)
```

Good for: cron pipelines, ETL jobs, solo developers, CI runners.

**When to avoid:** write-heavy workloads with many concurrent runs (SQLite
serialises writers; switch to Postgres when you feel contention).

---

### Single-host with analytics queries

You want `GROUP BY knot_id`, percentiles over lineage, or ad-hoc SQL.

```python
from pirn import Tapestry
from pirn.backends.sqlite import SQLiteStore
from pirn.backends.duckdb import DuckDBHistory
from pirn.backends.disk import LocalDiskDataStore

t = Tapestry(
    store=SQLiteStore("pirn.db"),
    history=DuckDBHistory("lineage.duckdb"),
    data=LocalDiskDataStore("./pirn-data"),
)
```

DuckDB is column-oriented: scanning 10 million lineage rows for a
`P99(duration_ms) GROUP BY knot_id` is an order of magnitude faster than
SQLite for the same query.

---

### Distributed — high-throughput runs

Multiple hosts writing runs concurrently, large intermediate values, full
durability.

```python
from pirn import Tapestry
from pirn.backends.postgres import PostgresStore, PostgresHistory
from pirn.backends.s3 import S3DataStore

store   = PostgresStore(dsn="postgresql://…")
history = PostgresHistory(dsn="postgresql://…")
data    = S3DataStore(bucket="my-pirn-data", prefix="runs/")

t = Tapestry(store=store, history=history, data=data)
```

Requires `pirn[postgres]` and `pirn[s3]`.

**Postgres pool sizing:** asyncpg defaults to `min_size=10, max_size=10`. Set
`min_size` / `max_size` by passing a pre-built pool to `PostgresStore(pool=…)`.
See `docs/deployment-sizing.md`.

---

### Distributed — separate OLTP + OLAP

Postgres for live writes, DuckDB (or a read replica) for analytics queries.
These are two separate backends — pirn writes to Postgres and you query
DuckDB separately (e.g. via DuckDB's Postgres scanner or a Postgres read replica
mounted as a DuckDB external table).

```python
from pirn import Tapestry
from pirn.backends.postgres import PostgresStore, PostgresHistory
from pirn.backends.valkey import ValKeyDataStore

# Writes go to Postgres
t = Tapestry(
    store=PostgresStore(dsn="postgresql://…"),
    history=PostgresHistory(dsn="postgresql://…"),
    data=ValKeyDataStore(url="redis://…", ttl=3600),
)

# Analytics queries run against a DuckDB file or Postgres read replica
# independently — not wired through Tapestry at all.
```

---

### Short-lived / serverless

Everything in ValKey with a TTL. Lineage goes to Postgres for durability;
intermediate values evict automatically.

```python
from pirn import Tapestry
from pirn.backends.postgres import PostgresHistory
from pirn.backends.valkey import ValKeyStore, ValKeyDataStore

t = Tapestry(
    store=ValKeyStore(url="redis://…", ttl=300),
    history=PostgresHistory(dsn="postgresql://…"),
    data=ValKeyDataStore(url="redis://…", ttl=3600),
)
```

---

## Quick reference

| Deployment | Store | History | DataStore |
|------------|-------|---------|-----------|
| Local dev | `InMemory` | `InMemory` | `InMemory` |
| Single-host durable | `SQLite` | `SQLite` | `LocalDisk` |
| Single-host analytics | `SQLite` | `DuckDB` | `LocalDisk` |
| Multi-host distributed | `Postgres` | `Postgres` | `S3` |
| Multi-host + analytics | `Postgres` | `Postgres` | `S3` |
| Serverless / short TTL | `ValKey` | `Postgres` | `ValKey` |

---

## Mixing backends

pirn does not constrain which backends you combine. Some unusual but valid
combinations:

- **`SQLiteStore` + `PostgresHistory`** — tapestry definition is local, but
  lineage is centralised (useful when many workers share one tapestry definition
  deployed per host).
- **`InMemoryStore` + `SQLiteHistory`** — tapestry rebuilt from code on every
  restart, but lineage is durable. Common in development when the tapestry
  schema is still evolving.
- **`PostgresStore` + `DuckDBHistory`** — Postgres for consistent writes,
  DuckDB for fast OLAP reads against lineage. You manage the Postgres → DuckDB
  sync separately (e.g. pg_logical or a nightly export).

---

## Extras

Install optional backend dependencies via pip extras:

```
pip install pirn[postgres]   # asyncpg
pip install pirn[valkey]     # valkey-glide
pip install pirn[s3]         # aiobotocore
pip install pirn[duckdb]     # duckdb
pip install pirn[otel]       # opentelemetry-sdk
```
