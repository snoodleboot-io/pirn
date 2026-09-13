# Extension Points

pirn is designed to be extended. Every major subsystem has a base class (subclass and override) — implement the interface, pass it to the `Tapestry` constructor, and the rest of the framework adapts automatically.

---

## Custom Knot subclasses

Subclass `Knot` and implement `async def process(self, ...) -> Any`:

```python
from pirn.core.knot import Knot
from pirn.core.optional import Optional
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

**Declaring inputs with a JSON schema instead of a signature.** A capability with no Python signature to introspect — an MCP-declared tool, an OpenAPI operation — declares its inputs with a JSON object schema, and the framework validates it with exactly the machinery a hinted knot gets:

```python
from pirn.core.knot_factory import KnotFactory, knot

search = KnotFactory.from_schema(
    "search",
    {"type": "object",
     "properties": {"query": {"type": "string", "minLength": 1},
                    "limit": {"type": "integer", "minimum": 1, "default": 10}},
     "required": ["query"]},
    call_remote_search,          # async or sync callable taking the inputs by keyword
)
node = search(query=upstream, limit=5, _config=KnotConfig(id="search"))

@knot(input_schema={...})        # the decorator form
async def lookup(**arguments): ...
```

The schema's `properties` are the declared inputs (parents or config, like any knot), `required` the ones construction must supply, each `default` fills an omitted input, and each property fragment becomes the `TypeAdapter` `validate_io` applies (`pirn/core/json_schema_type_builder.py` covers scalars, `enum`/`const`, nullable forms, `anyOf`/`oneOf`, arrays, nested objects, local `$ref`s and the numeric/string/array bounds). The generated class carries the schema as `_input_schema_override`, and `input_json_schema()` returns it unchanged.

**The inverse.** Every knot class can render the declaration its hints imply: `MyKnot.input_json_schema()` returns `{"type": "object", "properties": ..., "required": ...}` from the same annotations `validate_io` checks against — `T` for a `Knot | T` input, `Annotated` constraints kept, defaults recorded, `$defs` hoisted — and excludes Knot-typed and `PirnOpaqueValue`-typed inputs (a live resource is wired, never supplied by a caller) and the `**_` catch-all. A model-facing tool declaration derives from this rather than re-introspecting the signature.

---

## Custom TapestryStore

Implement the `TapestryStore` base class from `pirn.backends`:

```python
from pirn.backends.base.tapestry_store import TapestryStore
from pirn.core.knot import Knot
from pirn.backends.base.tapestry_snapshot import TapestrySnapshot


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
from pirn.backends.base.run_history import RunHistory
from pirn.core.run_result import RunResult
from pirn.core.knot_lineage import KnotLineage


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
from pirn.backends.base.data_store import DataStore


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

## Custom DataTransport

`DataStore` (above) is the content-addressed cache the framework's persistence layer
reads and writes. `DataTransport` is a separate, lower-level concern: it decides where a
single knot's output lives *between* the moment the upstream knot produces it and the
moment the downstream knot consumes it, on one edge of the graph. The executor calls
`write`/`read` — knot `process()` methods only ever see materialised Python values.

Implement `pirn.core.transport.data_transport.DataTransport`:

```python
from pirn.core.transport.data_transport import DataTransport
from pirn.core.transport.transport_handle import TransportHandle
from typing import Any


class RedisTransport(DataTransport):
    """Stash knot outputs in Redis for the lifetime of one run."""

    def __init__(self, redis_client):
        self._redis = redis_client

    @property
    def transport_id(self) -> str:
        return "redis"

    async def begin_run(self, run_id: str) -> None:
        pass  # nothing to allocate up front

    async def write(self, run_id: str, knot_id: str, value: Any) -> TransportHandle:
        key = f"pirn:{run_id}:{knot_id}"
        raw = pickle.dumps(value)
        self._redis.set(key, raw)
        return TransportHandle(
            transport_id=self.transport_id,
            key=key,
            type_name=f"{type(value).__module__}.{type(value).__qualname__}",
            size_bytes=len(raw),
        )

    async def read(self, handle: TransportHandle) -> Any:
        return pickle.loads(self._redis.get(handle.key))

    async def exists(self, handle: TransportHandle) -> bool:
        return bool(self._redis.exists(handle.key))

    async def end_run(self, run_id: str, *, success: bool) -> None:
        for key in self._redis.keys(f"pirn:{run_id}:*"):
            self._redis.delete(key)
```

Set it tapestry-wide, or override per knot via `KnotConfig.transport`:

```python
with Tapestry(transport=RedisTransport(redis_client)) as t:
    ...
```

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

## Admission control — AdmissionGate and ConcurrencyLimits

Before a ready knot (all its parents resolved) is dispatched, the engine offers it to an
`AdmissionGate`, which admits it only while capacity allows. This is how a run caps how
many knots execute at once, overall or per named group (e.g. "at most 4 concurrent OpenAI
calls" while everything else in the same run stays unbounded).

The supported extension point is **`ConcurrencyLimits`**, not writing a custom gate
directly — the engine already builds the right gate from it (`UnboundedAdmissionGate`
when nothing is set, `LimitedAdmissionGate` otherwise) and there is no `Tapestry(...)`
parameter to substitute a different gate implementation today:

```python
from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits

with Tapestry(concurrency=ConcurrencyLimits(max_in_flight=8, groups={"openai": 4})) as t:
    ...

# or per run, overriding the tapestry default — set on the RunRequest itself:
request = RunRequest(concurrency=ConcurrencyLimits(groups={"openai": 1}))
result = await tapestry.run(request)
```

A knot joins a group via `KnotConfig(concurrency_group="openai")`. Undefined groups fail
fast: once `ConcurrencyLimits` defines any group, a knot naming a group not in that set
raises `UndefinedConcurrencyGroupError` rather than silently running unbounded.

`pirn.engine.admission.admission_gate.AdmissionGate` itself is documented here because it
is the interface those two built-in implementations satisfy (subclass and override
`has_capacity`, `try_admit`, `release`, `wait_for_release`, `current_limit`, `set_limit`) —
useful reading if you need to understand or test admission behavior, even though wiring a
third implementation in requires engine-level changes today rather than a public
constructor argument.

### Runtime feedback — `AdmissionObserver` and `set_limit`

The caps are not fixed for the run's life. An `AdmissionObserver` hears every admission and
release of the run's gate, and every event carries the gate so the observer can move a cap
in reaction — the seam an adaptive concurrency controller (AIMD over a provider's throttling,
Little's-law over queue depth and hold time) is written against:

```python
from pirn.engine.admission.admission_event import AdmissionEvent
from pirn.engine.admission.admission_observer import AdmissionObserver


class BackOffOnThrottle(AdmissionObserver):
    """Halve the api cap on a throttled failure, creep it back up on success."""

    def on_release(self, event: AdmissionEvent) -> None:
        if event.group != "api" or event.group_limit is None:
            return
        if event.outcome == "err":
            event.gate.set_limit("api", max(1, event.group_limit // 2))
        elif event.waiting and event.group_limit < 16:
            event.gate.set_limit("api", event.group_limit + 1)


with Tapestry(concurrency=ConcurrencyLimits(groups={"api": 8}),
              admission_observers=[BackOffOnThrottle()]) as t:
    ...
result = await t.run(request, admission_observers=[...])   # per-run override; [] silences
```

- `AdmissionEvent` (`kind` `"admit"`/`"release"`, `run_id`, `knot_id`, `group`, `in_flight`, `group_in_flight`, `max_in_flight`, `group_limit`, `waiting` — knots of the same group still queued, `queued_seconds`, `held_seconds`, `outcome` `"ok"`/`"err"`/`"skipped"`/`"aborted"`, `gate`) is built by the engine's `AdmissionFeedback`, the one place that sees the gate's counters, the ready queue's depth, the ready time and the outcome together.
- `gate.set_limit(group, n)` (`group=None` for the run-wide cap) takes effect for every admission from then on and never touches a ticket already issued: lowering a cap below what is in flight refuses new admissions until enough slots come back. Groups cannot be added mid-run, and the unbounded gate (a run without `ConcurrencyLimits`) refuses with `AdmissionLimitError` — start with limits to steer them. `gate.current_limit(group)` reads the live cap.
- Hooks run synchronously on the engine's loop between scheduling steps, so keep them quick and never await; an exception raised by a hook is logged at WARNING and ignored — an observer can never break a run. A run with no observers pays nothing.

---

## Custom IdentityResolver

`IdentityResolver` supplies the actor string recorded against a run when
`RunRequest.actor` is not set explicitly — used for audit trails and lineage. The default
chain tries the environment, then the OS user; override it to integrate with your own
auth context (a request-scoped user, a service-account token, etc.):

```python
from pirn.core.identity.identity_resolver import IdentityResolver


class RequestContextIdentityResolver(IdentityResolver):
    """Resolve the actor from a request-scoped context var, if one is set."""

    def __init__(self, context_var):
        self._context_var = context_var

    def resolve(self) -> str | None:
        ctx = self._context_var.get(None)
        return ctx.user_id if ctx is not None else None
```

Pass it to `Tapestry`:

```python
with Tapestry(identity_resolver=RequestContextIdentityResolver(current_request_ctx)) as t:
    ...
```

`resolve()` returning `None` means "this resolver cannot determine an identity" — the
engine propagates `None` without raising, it does not fall through to another resolver
unless you compose one yourself (see `ChainedIdentityResolver`, which the default wiring
uses to try `EnvIdentityResolver` then `OsIdentityResolver` in order).

---

## Custom Emitters

Implement three async hooks (all optional — subclass the base and override what you need):

```python
from pirn.emitters.emitter import Emitter
from pirn.core.knot_lineage import KnotLineage
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

Implement `pirn.triggers.trigger.Trigger`:

```python
from pirn.triggers.trigger import Trigger, run_forever
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

Implement `pirn.streaming.streaming_source.StreamingSource`:

```python
from pirn.streaming.streaming_source import StreamingSource, run_stream
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
