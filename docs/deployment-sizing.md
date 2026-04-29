# Deployment sizing

## Postgres connection pool

asyncpg creates a pool with `min_size=10, max_size=10` by default. For most
pirn workloads you want to tune this:

```python
import asyncpg
from pirn.backends.postgres import PostgresHistory, PostgresStore

pool = await asyncpg.create_pool(
    dsn,
    min_size=5,
    max_size=20,        # tune to your concurrency level
    command_timeout=30, # seconds before a query is killed
)
store   = PostgresStore(pool=pool)
history = PostgresHistory(pool=pool)
```

### Sizing guidance

| scenario | min_size | max_size | notes |
|----------|----------|----------|-------|
| Single-process, low concurrency | 2 | 5 | CI, dev |
| Single-process, high concurrency | 5 | 20 | async workers, batch jobs |
| Multi-process (e.g. Celery workers) | 2 | 10 per process | multiply by worker count |
| Read-heavy analytics queries | 5 | 30 | lineage queries are cheap |

**Rule of thumb:** `max_size` should not exceed `(postgres max_connections / number of app processes) * 0.8`.
The default Postgres `max_connections` is 100; with 4 app processes that
gives `max_size = 20`.

### When to increase

- `asyncpg.TooManyConnectionsError` in logs → increase `max_size` or add
  PgBouncer in front.
- Pool acquire latency > 5 ms under load → increase `min_size` so warm
  connections are always available.

### When to decrease

- Postgres reports `too many connections` even at idle → decrease `min_size`.
- Memory pressure on the DB host → each connection uses ~5 MB; lower
  `max_size` across all clients.

## ValKey / Glide client

`valkey-glide` uses a single multiplexed connection by default. There is no
pool to configure for `ValKeyDataStore`; the client handles concurrent
requests via pipelining. For `ValKeyStore` the only configuration is the
`GlideClientConfiguration`:

```python
from glide import GlideClient, GlideClientConfiguration, NodeAddress

config = GlideClientConfiguration(
    [NodeAddress(host="localhost", port=6379)],
    request_timeout=250,   # ms; default is 250
    reconnect_strategy=...,
)
client = await GlideClient.create(config)
```

For cluster deployments use `GlideClusterClient` instead.

## SQLite

SQLite's single-writer model means all `record_run` calls are serialised.
For single-process deployments this is fine — the batched `executemany`
introduced in Phase 3 sustains ~5 000 lineage writes/sec in WAL mode.

To enable WAL mode (recommended for concurrent readers):

```python
import sqlite3
conn = sqlite3.connect("pirn.db")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")  # faster, still safe
from pirn.backends.sqlite import SQLiteHistory
history = SQLiteHistory(connection=conn)
```

For multi-process deployments, switch to `PostgresHistory`.

## S3 / MinIO

`S3DataStore` uses `aiobotocore` which manages its own connection pool via
`aiohttp`. The default pool size is 10 connections per session. To increase:

```python
import aiobotocore.session
from pirn.backends.s3 import S3DataStore

store = S3DataStore(
    bucket="my-bucket",
    region="us-east-1",
    # pass a pre-configured session to control pool size
)
```

For high-throughput scenarios (>100 concurrent puts) consider sharding across
multiple buckets or using a multipart upload threshold.
