# Extension Points

pirn is designed to be extended. Every major subsystem is a protocol — implement the interface, pass it to the `Tapestry` constructor, and the rest of the framework adapts automatically.

---

## Custom Knot subclasses

Subclass `Knot` and implement `async def process(self, ...) -> Any`:

```python
from pirn.core.knot import Knot, Optional
from pirn.core.knot_config import KnotConfig

class FilterByScore(Knot):
    async def process(
        self,
        records: list[dict],
        threshold: float,       # can come from parent or config
    ) -> list[dict]:
        return [r for r in records if r.get("score", 0) >= threshold]

filtered = FilterByScore(
    records=upstream_knot,          # parent — provides records at run time
    threshold=0.7,                  # config — constant value
    _config=KnotConfig(id="filter"),
)
```

**Rules for `process()`:**

- Parameters must not use reserved names `_config` or `tapestry`.
- `*args` and `**kwargs` are ignored by the wiring system.
- Raising any exception produces `Err`; the framework catches `BaseException`.
- Return type annotation is required if `validate_io=True` (the default).

**Combining with `Optional`:**

```python
class FetchPrefs(Optional, Knot):
    async def process(self, user_id: str) -> dict:
        return await prefs_api.get(user_id)  # might 404 or timeout
```

If `process()` raises, the outcome is converted from `Err` to `Skipped`, making failure tolerable for downstream consumers.

---

## Custom TapestryStore

Implement the `TapestryStore` protocol from `pirn.backends`:

```python
from pirn.backends import TapestryStore
from pirn.core.knot import Knot
from pirn.backends import TapestrySnapshot


class RedisStore:
    """TapestryStore backed by Redis (example)."""

    def register(self, knot: Knot) -> None:
        """Store the knot definition. Idempotent by identity."""
        serialised = pickle.dumps(knot)
        self._redis.set(f"knot:{knot.knot_id}", serialised, nx=True)

    def get(self, knot_id: str) -> Knot | None:
        raw = self._redis.get(f"knot:{knot_id}")
        return pickle.loads(raw) if raw else None

    def all(self) -> list[Knot]:
        keys = self._redis.keys("knot:*")
        return [pickle.loads(self._redis.get(k)) for k in keys]

    def snapshot(self) -> TapestrySnapshot:
        return TapestrySnapshot(knot_ids=[k.knot_id for k in self.all()])
```

For mid-run extension (`extensible=True`), also implement `SubscribableStore`:

```python
from pirn.backends.base.subscribable_store import SubscribableStore

class SubscribableRedisStore(RedisStore):
    def subscribe(self, callback) -> int:
        token = id(callback)
        self._subscribers[token] = callback
        return token

    def unsubscribe(self, token: int) -> None:
        self._subscribers.pop(token, None)
```

---

## Custom RunHistory

Implement `pirn.backends.RunHistory`:

```python
from pirn.backends import RunHistory
from pirn.core.run_result import RunResult
from pirn.core.lineage import KnotLineage


class BigQueryHistory:
    async def record_run(self, result: RunResult) -> None:
        rows = [self._lineage_to_row(rec) for rec in result.lineage]
        await self._bq_client.insert_rows_json(self._table, rows)

    async def get_run(self, run_id: str) -> RunResult | None:
        ...

    async def query_lineage_by_output_hash(
        self, output_hash: str
    ) -> list[KnotLineage]:
        query = f"""
            SELECT * FROM `{self._table}`
            WHERE output_hash = @hash
        """
        ...

    async def query_lineage_by_input_hash(
        self, input_hash: str
    ) -> list[KnotLineage]:
        ...

    async def query_lineage_by_knot_id(
        self, knot_id: str
    ) -> list[KnotLineage]:
        ...
```

---

## Custom DataStore

Implement `pirn.backends.DataStore`:

```python
from pirn.backends import DataStore


class GCSDataStore:
    def __init__(self, bucket: str, prefix: str = "pirn/"):
        self._bucket = bucket
        self._prefix = prefix

    async def put(self, content_hash: str, value: Any) -> None:
        blob_name = self._prefix + content_hash
        data = pickle.dumps(value)
        await self._gcs.upload_blob(self._bucket, blob_name, data)

    async def get(self, content_hash: str) -> Any:
        blob_name = self._prefix + content_hash
        data = await self._gcs.download_blob(self._bucket, blob_name)
        return pickle.loads(data)

    async def has(self, content_hash: str) -> bool:
        blob_name = self._prefix + content_hash
        return await self._gcs.blob_exists(self._bucket, blob_name)

    async def scrub(self, content_hash: str) -> None:
        blob_name = self._prefix + content_hash
        await self._gcs.delete_blob(self._bucket, blob_name)
```

!!! warning "Pickle"
    Custom `DataStore` implementations that use pickle inherit the same security caveat as the built-in ones: only use them when the backing store is not writable by adversaries.

---

## Custom Dispatchers

Implement `pirn.engine.dispatchers.Dispatcher`:

```python
from pirn.engine.dispatchers.dispatcher import Dispatcher
from pirn.core.knot import Knot
from pirn.core.result import Result
from collections.abc import Mapping


class KubernetesJobDispatcher:
    """Submits each knot as a Kubernetes Job and waits for completion."""

    @property
    def name(self) -> str:
        return "KubernetesJobDispatcher"

    async def dispatch(self, knot: Knot, inputs: Mapping) -> Result:
        job_spec = self._build_job_spec(knot, inputs)
        job_name = await self._k8s.create_job(job_spec)
        return await self._wait_for_result(job_name)

    def _build_job_spec(self, knot: Knot, inputs: Mapping) -> dict:
        ...
```

Pass it to `Tapestry`:

```python
dispatcher = KubernetesJobDispatcher(namespace="pirn-jobs")
with Tapestry(dispatcher=dispatcher) as t:
    ...
```

Or override per-run:

```python
result = await tapestry.run(request, dispatcher=KubernetesJobDispatcher())
```

---

## Custom Emitters

Implement three async hooks (all optional — subclass the base and override what you need):

```python
from pirn.emitters.base import Emitter
from pirn.core.lineage import KnotLineage
from pirn.core.run_result import RunResult
from pirn.managers.status_event import StatusEvent


class DatadogEmitter(Emitter):
    def __init__(self, statsd_client):
        self._statsd = statsd_client

    async def on_status(self, event: StatusEvent) -> None:
        # High-frequency — called on every knot state transition
        pass  # skip for Datadog to avoid metric cardinality explosion

    async def on_lineage(self, record: KnotLineage) -> None:
        # Called once per knot after it completes — right for metrics
        self._statsd.increment(
            "pirn.knot.runs",
            tags=[f"knot:{record.knot_id}", f"outcome:{record.outcome}"],
        )
        if record.started_at and record.finished_at:
            ms = (record.finished_at - record.started_at).total_seconds() * 1000
            self._statsd.histogram(
                "pirn.knot.duration_ms",
                ms,
                tags=[f"knot:{record.knot_id}"],
            )

    async def on_run_result(self, result: RunResult) -> None:
        self._statsd.increment(
            "pirn.run.completed",
            tags=[f"succeeded:{result.succeeded}"],
        )
```

Register:

```python
t = Tapestry(emitters=[DatadogEmitter(statsd)])
# or
t.add_emitter(DatadogEmitter(statsd))
```

!!! note "Emitters must not raise"
    Exceptions in emitters are swallowed (or logged at WARNING, depending on `emitter_error_policy`). A broken emitter should never affect the pipeline run itself. Schedule long-running work as background tasks, not inline.

---

## Custom Triggers

Implement `pirn.triggers.base.Trigger`:

```python
from pirn.triggers.base import Trigger, run_forever
from pirn.core.run_request import RunRequest
from collections.abc import AsyncIterator
import boto3


class SQSTrigger:
    """Fire one run per SQS message."""

    def __init__(self, queue_url: str, region: str = "us-east-1"):
        self._queue_url = queue_url
        self._sqs = boto3.client("sqs", region_name=region)
        self._running = True

    @property
    def name(self) -> str:
        return "SQSTrigger"

    async def stream(self) -> AsyncIterator[RunRequest]:
        while self._running:
            messages = self._sqs.receive_message(
                QueueUrl=self._queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,
            ).get("Messages", [])
            for msg in messages:
                params = json.loads(msg["Body"])
                yield RunRequest(parameters=params)
                self._sqs.delete_message(
                    QueueUrl=self._queue_url,
                    ReceiptHandle=msg["ReceiptHandle"],
                )

    async def close(self) -> None:
        self._running = False
```

Drive with `run_forever`:

```python
trigger = SQSTrigger(queue_url="https://sqs.us-east-1.amazonaws.com/...")
await run_forever(trigger, tapestry, on_result=handle_result)
```

---

## Custom StreamingSources

Implement `pirn.streaming.base.StreamingSource`:

```python
from pirn.streaming.base import StreamingSource, run_stream
from collections.abc import AsyncIterator


class WebSocketSource:
    """Stream events from a WebSocket connection."""

    def __init__(self, ws_uri: str, parameter_name: str = "event"):
        self._uri = ws_uri
        self._param = parameter_name
        self._ws = None

    @property
    def name(self) -> str:
        return "WebSocketSource"

    @property
    def parameter_name(self) -> str:
        return self._param

    async def stream(self) -> AsyncIterator:
        import websockets
        async with websockets.connect(self._uri) as ws:
            self._ws = ws
            async for message in ws:
                yield json.loads(message)

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
```

Drive with `run_stream`:

```python
source = WebSocketSource("wss://events.example.com/stream")
await run_stream(source, tapestry, on_result=handle)
```

---

**See also:** [Architecture Overview](overview.md), [Execution Model](execution-model.md), [API — Backends](../api/backends.md)
