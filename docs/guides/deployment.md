# Deployment

This guide covers sizing guidance for different deployment scales, connection pool tuning, and operational considerations for running pirn in production.

---

## Postgres connection pool

`asyncpg` creates a connection pool that is shared by all concurrent `tapestry.run()` calls within a process. Tune it based on your concurrency level and the Postgres server's `max_connections`.

```python
import asyncpg
from pirn.backends.postgres import PostgresStore, PostgresHistory

pool = await asyncpg.create_pool(
    dsn,
    min_size=5,
    max_size=20,           # scale to your concurrency
    command_timeout=30,    # seconds before a query is killed
)

t = Tapestry(
    store=PostgresStore(pool=pool),
    history=PostgresHistory(pool=pool),
)
```

### Pool sizing table

| Scenario | min_size | max_size | Notes |
|----------|----------|----------|-------|
| Single-process, low concurrency | 2 | 5 | CI, dev, notebooks |
| Single-process, high concurrency | 5 | 20 | Async workers, batch jobs |
| Multi-process (e.g. Celery workers) | 2 | 10 per process | Multiply by worker count |
| Read-heavy analytics | 5 | 30 | Lineage queries are cheap |

**Rule of thumb:** `max_size` should not exceed `(postgres max_connections / number of app processes) × 0.8`. The default Postgres `max_connections` is 100. With 4 app processes: `max_size = (100 / 4) × 0.8 = 20`.

### When to tune up

- `asyncpg.TooManyConnectionsError` in logs → increase `max_size` or add PgBouncer in front.
- Pool acquire latency > 5 ms under load → increase `min_size` so warm connections are always available.

### When to tune down

- Postgres reports `too many connections` even at idle → decrease `min_size`.
- Memory pressure on the DB host → each connection uses ~5 MB; lower `max_size` across all clients.

---

## SQLite sizing

SQLite's single-writer model means all `record_run` calls are serialised. For single-process deployments this is fine — the batched `executemany` in `SQLiteHistory` sustains approximately 5,000 lineage writes/second in WAL mode.

Enable WAL mode for best performance:

```python
import sqlite3
from pirn.backends.sqlite import SQLiteHistory, SQLiteStore

conn = sqlite3.connect("pirn.db")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")  # faster; still crash-safe

history = SQLiteHistory(connection=conn)
store = SQLiteStore(connection=conn)
```

For multi-process deployments (multiple workers writing concurrently), switch to `PostgresHistory`.

---

## ValKey / Glide client

`valkey-glide` uses a single multiplexed connection per client instance. There is no pool to configure; the client handles concurrent requests via pipelining. Configure the connection at construction:

```python
from glide import GlideClient, GlideClientConfiguration, NodeAddress

config = GlideClientConfiguration(
    [NodeAddress(host="localhost", port=6379)],
    request_timeout=250,    # ms; default is 250
)
client = await GlideClient.create(config)
```

For Redis Cluster deployments, use `GlideClusterClient` instead.

---

## S3 / MinIO

`S3DataStore` uses `aiobotocore`, which manages its own connection pool via `aiohttp`. The default pool size is 10 connections per session. For high-throughput scenarios (>100 concurrent puts), consider:

- Sharding across multiple buckets by hash prefix.
- Tuning `aiohttp.ClientSession` connector limits.
- Using multipart upload for large values (configured via `multipart_threshold` in the store constructor).

---

## Distributed dispatchers

### Celery workers

Each Celery worker process is a separate Python interpreter. Ensure:

- `pirn` and all knot packages are importable on the worker.
- The Celery app is configured with `task_serializer="pickle"` and `accept_content=["pickle"]`.
- Knot classes are defined at module scope so they are pickle-serializable across processes.

```python
from celery import Celery
from pirn.engine.dispatchers.celery_dispatcher import register_celery_worker_task

app = Celery("pirn", broker="redis://localhost:6379/0")
app.conf.update(
    task_serializer="pickle",
    accept_content=["pickle"],
    result_serializer="pickle",
)
register_celery_worker_task(app)
```

Worker count: start with `(CPU cores × 2) + 1` for IO-bound pipelines. For CPU-bound knots, use `prefork` concurrency equal to core count.

### Dask

Use `DaskDispatcher` for in-process or cluster Dask:

```python
from dask.distributed import Client
from pirn.engine.dispatchers.dask_dispatcher import DaskDispatcher

client = Client("tcp://scheduler:8786")
dispatcher = DaskDispatcher(client=client)

t = Tapestry(dispatcher=dispatcher)
```

Dask uses `cloudpickle` for serialisation — handles lambdas and locally-defined functions. Workers must have `pirn` importable.

### Ray

```python
import ray
from pirn.engine.dispatchers.ray_dispatcher import RayDispatcher

ray.init(address="ray://head:10001")
dispatcher = RayDispatcher()

t = Tapestry(dispatcher=dispatcher)
```

Ray also uses `cloudpickle`. Knots that are remote tasks must be importable on Ray workers.

---

## Deployment patterns

### Scheduled batch (cron)

Single host, SQLite, no infrastructure:

```python
# run.py — invoked by cron
import asyncio
from pirn import Tapestry, RunRequest
from pirn.backends.sqlite import SQLiteStore, SQLiteHistory
from pirn.backends.disk import LocalDiskDataStore

async def main():
    t = Tapestry(
        store=SQLiteStore("pirn.db"),
        history=SQLiteHistory("pirn.db"),
        data_store=LocalDiskDataStore("./pirn-data"),
    )
    # ... build tapestry, run ...

asyncio.run(main())
```

### Always-on service (webhook trigger)

```python
import uvicorn
from pirn import Tapestry
from pirn.triggers import WebhookTrigger

trigger = WebhookTrigger(path="/run")
# trigger.app is a Starlette ASGI app

# Mount behind an authenticating proxy (nginx, Caddy, API gateway)
# before exposing to any network. WebhookTrigger has no built-in auth.
uvicorn.run(trigger.app, host="127.0.0.1", port=8080)
```

!!! warning "WebhookTrigger has no built-in authentication"
    Always place an authenticating reverse proxy in front of `WebhookTrigger` before exposing it to any network.

### Event-driven (Kafka trigger)

```python
from pirn.triggers import KafkaTrigger, run_forever

trigger = KafkaTrigger(
    topic="orders",
    bootstrap_servers="kafka:9092",
    group_id="pirn-worker",
)

await run_forever(trigger, tapestry, on_result=handle_result)
```

### Streaming ETL

```python
from pirn.streaming import FileTailSource, run_stream

source = FileTailSource("/var/log/app.log", parameter_name="line")
await run_stream(source, tapestry, on_result=handle)
```

---

## Health checks

Use `tapestry.check()` to validate the tapestry structure before starting a service:

```bash
tapestry-check pipeline.yaml --known-callables registry:REGISTRY
```

This checks for cycles, unresolved callable references, and missing parameters without executing the pipeline.

---

**See also:** [Backends](backends.md), [Observability](observability.md)
