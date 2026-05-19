`pirn.domains.connectors` provides configuration objects, connection pools, and knots for every external system pirn can read from or write to — it does not perform domain transformations; connectors move raw bytes and records, not domain payloads.

---

## Mental model

Every connector follows the same three-layer pattern:

1. **Config** — a `ConnectionConfig` subclass holding credentials and DSN fields. Passed as a config constant to a pool or knot — never wired as a parent.
2. **Pool / Client** — a `DatabaseConnectionPool`, `ObjectStore`, `MessageBroker`, or API client that holds a live connection. Created once and passed as config to multiple knots.
3. **Knot** — a `Source` or `Sink` in `knots/` that uses the pool to read or write. Wired into the tapestry like any other knot.

All pools, stores, and clients inherit from `PirnOpaqueValue` — pirn serialises them by identity, keeping content-addressing cache stable across runs.

---

## Source map

```
pirn/domains/connectors/
├── connection_config.py         ConnectionConfig          — base: host, port, database, credentials fields
├── database_connection_pool.py  DatabaseConnectionPool    — base: acquire(), release(), close()
├── object_store.py              ObjectStore               — base: read(), write(), list(), delete()
├── message_broker.py            MessageBroker             — base: publish(), consume(), close()
├── file_format.py               FileFormat                — base: encode()/decode() for a single format
├── dsn_scrubber.py              dsn_scrubber()            — strips credentials from DSN strings before logging
├── api_client.py                ApiClient                 — base for REST API clients (SaaS connectors)
├── connection_config_decorator.py  @connection_config     — decorator: register a config class for auto-discovery
├── knots/                       source/sink knots         — → see AGENTIC_USE.md
├── capabilities/                capability interfaces     — → see AGENTIC_USE.md
├── databases/                   DB configs + pools        — → see AGENTIC_USE.md
├── file_formats/                FileFormat implementations — → see AGENTIC_USE.md
├── messaging/                   messaging clients         — → see AGENTIC_USE.md
├── object_storage/              object store impls        — → see AGENTIC_USE.md
├── streaming/                   streaming broker impls    — → see AGENTIC_USE.md
├── saas/                        SaaS API clients          — → see AGENTIC_USE.md
├── timeseries/                  time-series DB configs    — → see AGENTIC_USE.md
├── document/                    document store connectors — → see AGENTIC_USE.md
├── graph/                       graph DB connectors       — → see AGENTIC_USE.md
├── bi_catalog/                  BI/catalog connectors     — → see AGENTIC_USE.md
├── transports/                  low-level transport impls — internal
└── observability/               observability connectors  — → see AGENTIC_USE.md
```

---

## Canonical pattern

### Query a database

```python
from pirn import Tapestry, KnotConfig, RunRequest
from pirn.domains.connectors.databases.postgres_config import PostgresConfig
from pirn.domains.connectors.databases.postgres_pool import PostgresPool
from pirn.domains.connectors.knots.database_query_source import DatabaseQuerySource

config = PostgresConfig(host="db", port=5432, database="mydb", user="app", password="secret")
pool   = PostgresPool(config=config)

with Tapestry() as t:
    rows = DatabaseQuerySource(
        pool=pool,
        query="SELECT id, name FROM users WHERE active = true",
        _config=KnotConfig(id="users"),
    )
    ProcessRows(rows=rows, _config=KnotConfig(id="process"))

result = await t.run(RunRequest())
await pool.close()
```

### Write to a database

```python
from pirn.domains.connectors.knots.database_execute_sink import DatabaseExecuteSink

with Tapestry() as t:
    processed = ProcessKnot(_config=KnotConfig(id="process"))
    DatabaseExecuteSink(
        pool=pool,
        statement="INSERT INTO results (id, score) VALUES (:id, :score)",
        rows=processed,
        _config=KnotConfig(id="write"),
    )
```

### Read from object storage

```python
from pirn.domains.connectors.object_storage.s3_store import S3Store
from pirn.domains.connectors.knots.object_store_read_source import ObjectStoreReadSource

store = S3Store(bucket="my-bucket", prefix="data/")

with Tapestry() as t:
    raw = ObjectStoreReadSource(store=store, key="input.parquet", _config=KnotConfig(id="read"))
```

### Publish to a message broker

```python
from pirn.domains.connectors.streaming.kafka_broker import KafkaBroker
from pirn.domains.connectors.knots.message_broker_publish_sink import MessageBrokerPublishSink

broker = KafkaBroker(topic="results", producer=my_kafka_producer)

with Tapestry() as t:
    result = ProcessKnot(_config=KnotConfig(id="process"))
    MessageBrokerPublishSink(broker=broker, message=result, _config=KnotConfig(id="publish"))
```

---

## Sub-package index

| Sub-package | What it contains | Guide |
|---|---|---|
| `knots/` | Generic source/sink knots for DB, object store, message broker | [AGENTIC_USE.md](knots/AGENTIC_USE.md) |
| `databases/` | ConnectionConfig + Pool for 13 databases | [AGENTIC_USE.md](databases/AGENTIC_USE.md) |
| `file_formats/` | FileFormat implementations for 90+ formats | [AGENTIC_USE.md](file_formats/AGENTIC_USE.md) |
| `object_storage/` | ObjectStore for S3, GCS, Azure Blob, HDFS, local | [AGENTIC_USE.md](object_storage/AGENTIC_USE.md) |
| `streaming/` | MessageBroker for Kafka, Kinesis, RabbitMQ, Pub/Sub, ValKey, Azure Service Bus | [AGENTIC_USE.md](streaming/AGENTIC_USE.md) |
| `messaging/` | API clients for Teams, Discord, Telegram, PagerDuty, Google Chat | [AGENTIC_USE.md](messaging/AGENTIC_USE.md) |
| `saas/` | API clients for Stripe, Salesforce, HubSpot, Jira, GitHub, and more | [AGENTIC_USE.md](saas/AGENTIC_USE.md) |
| `timeseries/` | Config + Pool for InfluxDB, TimescaleDB, QuestDB, kdb+, VictoriaMetrics | [AGENTIC_USE.md](timeseries/AGENTIC_USE.md) |
| `document/` | Document store connectors | [AGENTIC_USE.md](document/AGENTIC_USE.md) |
| `graph/` | Graph DB connectors | [AGENTIC_USE.md](graph/AGENTIC_USE.md) |
| `bi_catalog/` | BI and data catalog connectors (dbt, Fivetran, Airbyte) | [AGENTIC_USE.md](bi_catalog/AGENTIC_USE.md) |
| `observability/` | Observability connectors | [AGENTIC_USE.md](observability/AGENTIC_USE.md) |

---

## Anti-patterns

### Passing a `ConnectionConfig` directly to a knot

`ConnectionConfig` is a credentials holder, not a live connection. Knots require a pool (`DatabaseConnectionPool`) or store (`ObjectStore`) — not the config. Create the pool from the config first, then pass the pool.

### Creating a new pool per run

Pools hold live connections. Creating one inside `Tapestry()` per run is expensive and can exhaust database connection limits. Create pools once at application startup and pass them as config constants to multiple tapestries.

### Logging a DSN string directly

DSNs contain credentials. Always pass DSN strings through `dsn_scrubber(dsn)` before logging or including in error messages.

---

## Constraints and gotchas

- **All pools, stores, and clients are `PirnOpaqueValue`.** They are not inspected by pirn's content-addressing. The same pool object across two runs produces the same cache key regardless of connection state.
- **Connector extras are fine-grained.** Each database or SaaS system may require its own extra (e.g. `pirn[postgres]`, `pirn[snowflake]`). Check `pyproject.toml` for the exact extra name before installing.
- **`FileFormat` implementations are stateless.** They encode and decode; they do not hold connections. Pass them as config constants without pooling.

---

## Quick reference

| Task | How |
|------|-----|
| Query a database | `DatabaseQuerySource(pool=pool, query=..., _config=...)` |
| Execute a statement | `DatabaseExecuteSink(pool=pool, statement=..., rows=..., _config=...)` |
| Read from object storage | `ObjectStoreReadSource(store=store, key=..., _config=...)` |
| Write to object storage | `ObjectStoreWriteSink(store=store, key=..., data=..., _config=...)` |
| List object storage keys | `ObjectStoreListSource(store=store, prefix=..., _config=...)` |
| Publish to a message broker | `MessageBrokerPublishSink(broker=broker, message=..., _config=...)` |
| Scrub credentials from a DSN | `dsn_scrubber(dsn_string)` |

---

*See also: [pirn AGENTIC_USE.md](../../../AGENTIC_USE.md)*
