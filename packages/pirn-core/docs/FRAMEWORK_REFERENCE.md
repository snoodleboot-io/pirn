# pirn-core Framework Reference

**Audience:** authors building on top of pirn-core (especially `pirn-agents`).
**Purpose:** the authoritative catalog of core's base classes, interfaces, and idioms, so downstream packages *extend* the framework instead of reinventing it.

> This reference was produced by a full sweep of `packages/pirn-core/pirn`. Every pattern below is verified against the actual source. Where a downstream package (pirn-agents) diverges, the divergence is a bug, not a style preference.

---

## 1. The mental model

pirn is a **content-addressed dataflow framework**. You declare a graph of `Knot`s inside a `Tapestry`; the engine executes them, moving values between them over a `DataTransport`, recording lineage, and returning a `Result` per knot.

Five concepts you must internalize before writing anything:

| Concept | What it is | File |
|---|---|---|
| **Knot** | the unit of work; you subclass it and implement `process()` | `core/knot.py` |
| **Tapestry** | the pipeline container + context manager; knots self-register into it | `tapestry.py` |
| **Result** | every knot invocation yields `Ok \| Err \| Skipped` | `core/result.py` |
| **PirnOpaqueValue** | the contract that lets a live/non-pydantic value cross the graph | `core/pirn_opaque_value.py` |
| **DataTransport** | the pluggable layer that moves a knot's output to its consumers | `core/transport/data_transport.py` |

### 1.1 The Knot construction contract (read this twice)

A knot is constructed with **keyword arguments that are introspected against its `process()` signature**. For each kwarg (`core/knot.py`):

- **If the value is a `Knot`** → it becomes a **parent** (a dependency). At run time this knot's `process()` receives the parent's *resolved output*, not the knot.
- **If the value is not a `Knot`** → it is **config** (a constant captured at build time).
- Framework metadata travels through one reserved kwarg: `_config=KnotConfig(id=...)`. The `id` is **required** — nothing is auto-generated.
- `process()` **must** accept `**_: Any` (enforced by `Knot.__init_subclass__`) and **must not** declare `*args`. The engine calls `process()` with keyword arguments only.

**A schema can stand in for the signature.** `KnotFactory.from_schema(name, input_schema, process)` / `@knot(input_schema=...)` declare the inputs of a knot that has no Python signature (an MCP-declared tool) with a JSON object schema; `Knot._input_schema_override` carries it and `JsonSchemaTypeBuilder` turns each property into the `TypeAdapter` `validate_io` applies. The inverse, `Knot.input_json_schema()`, renders any knot's hinted inputs as the same kind of schema — the source for model-facing declarations.

**The `Knot | T` union is load-bearing.** When a `process()` parameter is hinted `Knot | T`, passing a scalar `T` causes the framework to auto-wrap it in a `Parameter(default=value)` **graph node** (`core/knot.py`, the `_coercible_params` path). This is what turns an externally-constructed resource into a first-class node with lineage — rather than invisible config. This is the entire basis of the **vending-knot idiom** (§4.1).

### 1.2 Knots don't guard their own types

By the time `process()` runs, the engine has already resolved parents, merged config, and — when `KnotConfig.validate_io` is set — validated every input against its declared type via a pydantic `TypeAdapter`. That validation works because opaque values supply an `is_instance_schema` (§1.3). **Therefore `process()` operates on already-contract-validated inputs.** Writing `isinstance`/`TypeError` guards inside `process()` re-does the framework's job and signals a misunderstanding of the contract. Express *what the knot does*, not type-checking.

### 1.3 PirnOpaqueValue — the contract for live values

Many values wrap engine-specific or non-pydantic state (DB pools, SDK clients, live drivers, lazy frames). `PirnOpaqueValue` (`core/pirn_opaque_value.py`) is a mixin that gives such a value a pydantic core schema of `is_instance_schema(cls)` plus a pluggable serializer (`_pirn_audit_dict()`, default `<TypeName@hex>`). 

**Rule:** *any* type that wraps live/non-pydantic state and is passed as a Knot config value or crosses the IO boundary **must** inherit `PirnOpaqueValue`. Without it, pydantic IO validation tries to descend into engine internals and content-addressing is unstable. This is why every provider/connector/store interface below inherits it.

---

## 2. The interface convention (NOT Protocol, NOT ABC)

Core defines **every** interface as a **plain base class whose contract methods raise `NotImplementedError`**. Confirmed uniform across the whole tree:

```python
class LLMProvider(PirnOpaqueValue):
    async def chat(self, messages, *, model=None, ...) -> Mapping[str, Any]:
        raise NotImplementedError(f"{type(self).__name__} must implement chat()")
```

> **Note:** `LLMProvider`/`EmbeddingProvider` are shown here only as exemplars of this convention — the contracts themselves no longer live in core. They are owned by each consuming domain (`pirn_agents`; `pirn_health` for the LLM wire, `pirn_ml` for the embedding wire), which still inherit `PirnOpaqueValue` from core and follow this exact `NotImplementedError`-base style. Core keeps in-tree interface bases such as `Trigger`, `DataTransport`, and `DataStore`.

- **No `typing.Protocol`.** Core has zero. Structural typing gives no `is_instance_schema` (breaks opaque values), and `@runtime_checkable` + `isinstance` is signature-blind (matches any object with the attribute *names*).
- **No `abc.ABC`/`@abstractmethod`.** The house style is the `NotImplementedError` base class. (ABC is tolerated but not used in core.)
- Docstrings sometimes say "protocol" informally (e.g. `triggers/base.py`) — the *code* is always a `NotImplementedError` base class.
- Stateful interfaces additionally inherit `PirnOpaqueValue`.

**Three shapes to distinguish:**
1. **Interface base** — contract methods raise `NotImplementedError` (`LLMProvider`, `Trigger`, `DataTransport`, `DataStore`).
2. **Capability interface (mixin)** — a narrow opt-in surface a concrete type *also* inherits, so consumers depend on the capability not the vendor (`TableSource`, `RecordWriter` — §4.2).
3. **Value object** — a frozen dataclass, `PirnOpaqueValue` if it holds non-pydantic fields, with `__post_init__` invariants (`KnotConfig`, `TransportHandle`, lineage records).

---

## 3. Subsystem catalog

### 3.1 Core primitives — `core/`
| Type | Kind | Inherits | Contract / role |
|---|---|---|---|
| `Knot` | interface-base | — | `async process(**_) -> Any` (raises); framework `__call__` resolves parents, validates IO, returns `Result`; immutable after `__init__` (`__setattr__` guard) |
| `Ok[T]` / `Err` / `Skipped` | value-object | — | the outcome algebra; `Result = Ok[T] \| Err \| Skipped` (`core/result.py`). **Everything that can succeed/fail/skip uses this — do not invent parallel status enums.** |
| `PirnOpaqueValue` | mixin | — | `is_instance_schema` + `_pirn_audit_dict()`; the live-value contract |
| `Parameter` | concrete Knot | `Knot` | wraps a scalar as a graph node (the `Knot \| T` coercion target) |
| `KnotFactory` / `@knot` | factory | — | `core/knot_factory.py` — a function's signature becomes a Knot's input contract; `from_schema(name, input_schema, process)` / `@knot(input_schema=)` do the same from a JSON object schema |
| `JsonSchemaTypeBuilder` | helper | — | `core/json_schema_type_builder.py` — JSON-schema fragment → Python type for `TypeAdapter` (scalars, enum/const, nullable, anyOf/oneOf, arrays, objects as `TypedDict`, local `$ref`, bounds). **Do not write a second schema→validator or signature→schema compiler.** |
| `KnotConfig` | config | — | `id` (required), `validate_io`, `error_policy`, `transport`, `concurrency_group`, `timeout`, `retry` |
| `KnotRetryPolicy` | value-object | — | `core/knot_retry_policy.py` — frozen backoff schedule (`max_attempts`, `base_delay`, `max_delay`, `multiplier`, `jitter`, `max_retry_after`) plus `is_retryable` / `retry_after` predicates over the failed attempt's `ExceptionRecord`. Set on `KnotConfig.retry`; the **engine** runs the loop (§3.5). **Do not write a retry loop inside a knot.** |
| `RunRequest` / `RunResult` / `RunContext` | value-object | — | a run's input/output/ambient context; `RunContext.nesting` is the run's `RunNesting` frame |
| `RunNesting` | value-object | — | `core/run_nesting.py` — where a run sits in the nested-run tree (`depth`, enclosing `run_ids`, container `path`, tightest `max_depth`); `RunNesting.current()` inside a knot. `Tapestry(max_nesting_depth=n)` turns the guard on: `NestingDepthExceededError` / `NestedRunCycleError` as the container knot's `Err`. **Do not carry a recursion counter through agent code.** |
| `ErrorPolicy` | enum/policy | — | how upstream `Err` propagates (`RECEIVE_ERRORS` etc.) |
| `IdentityResolver` | interface-base | — | `core/identity/` — `resolve()` who's running; `chained/env/os/static/null` implementations |

### 3.2 Nodes — `nodes/`
All subclass `Knot`. These are the graph-shape primitives.
| Type | Role |
|---|---|
| `Source` / `Sink` | graph entry / exit |
| `Aggregator` | fan-in of multiple parents |
| `Reduce` | fold over a collection |
| `Continuation` | deferred/streaming continuation |
| `SubTapestry` / `LoopSubTapestry` | nest a tapestry as a node / iterate it; the loop's `astep` / `afold` are awaited (override them, or declare `step`/`fold` as `async def`) so an iteration can sleep, check a budget or call a model between turns |
| `Branch` (`branch/`) | conditional path selection; `BranchOutput` |
| `Gate` (`gate/`) | pass/close gate; decision is `predicate=` (callable) or `check=` (a `Check` knot) |
| `Check` (`check.py`) | the predicate half of a `Gate`: any parents → `bool`, enforced. **The core name for a boolean verdict knot; agents' `*Check` knots subclass it, not `Knot`.** |
| `Map` / `ZipMap` / `DictMap` (`map_markers.py`) | fan-out markers on a `process()` input → per-element execution |

**Idiom:** distribution is declarative — annotate an input with a `Map`/`ZipMap`/`DictMap` marker and the framework runs `process()` once per element (`Knot._fan_out`).

### 3.3 Triggers + Streaming — `triggers/`, `streaming/`
| Type | Kind | Contract |
|---|---|---|
| `Trigger` | interface-base | `name` (prop), `stream() -> AsyncIterator[RunRequest]`, `async close()` — all raise `NotImplementedError` |
| `Cron` / `Http` / `Kafka` / `Valkey` triggers | concrete | async generators yielding one `RunRequest` per event |
| `run_forever(trigger, tapestry, *, on_result, on_error)` | driver fn | pulls requests, calls `tapestry.run` per event, `close()`s on exit — a legitimate module-level driver |
| `StreamingSource` (`streaming/base.py`) | interface-base | streaming input adapters; `trigger_adapter.py` bridges a stream to the trigger loop |

**Idiom (the trigger loop):** a `Trigger` is an async generator of `RunRequest`s; `run_forever` is the runtime that consumes them and runs the tapestry. Downstream event-driven agents should implement `Trigger`, not hand-roll a consume loop.

### 3.4 Transport + Serializers — `core/transport/`
| Type | Kind | Contract |
|---|---|---|
| `DataTransport` | interface-base | `transport_id` (prop), `async begin_run(run_id)`, `async write(run_id, knot_id, value) -> TransportHandle`, `async read(handle)`, `async end_run(run_id)` — all raise |
| `InlineTransport` / `FilesystemTransport` / `DualWriteTransport` / `SmartTransport` | concrete | in-memory / on-disk / mirrored / size-adaptive movement |
| `TransportHandle` | value-object | opaque pointer to a written value (carries `transport_id`) |
| `Serializer` | interface-base | `core/transport/serializers/serializer.py`; `SerializerRegistry` selects by type; `numpy`/`pickle` impls |

**Idiom:** transport is set on the `Tapestry` (applies to every edge) or overridden per-knot via `KnotConfig.transport`; **knots never call `write`/`read`** — they always see materialized Python values. Large/opaque values move via transport, not by being embedded in lineage.

### 3.5 Engine + Dispatchers + Shed — `engine/`
| Type | Kind | Contract |
|---|---|---|
| `Dispatcher` (`dispatchers/dispatcher.py`) | interface-base | submits knot execution to a backend; `local`/`thread`/`ray`/`dask`/`celery` impls |
| `Engine` (`engine.py`) | engine | drives `Knot.__call__`, applies `ErrorPolicy`, subscribes emitters |
| `GovernedDispatch` (`governed_dispatch.py`) | engine | the dispatch path between `Engine` and `Dispatcher`: applies `KnotConfig.timeout` (`asyncio.wait_for` → `Err(KnotTimeoutError)`) and `KnotConfig.retry` (re-dispatch after backoff on the loop; attempt count → `KnotLineage.extra["attempts"]`). Dispatchers stay one `dispatch()`; `Knot.__call__` stays one attempt |
| `Shed` / `Edge` (`shed/`) | engine | the resolved execution graph the engine walks |
| `AdmissionGate` (`admission/`) | interface-base | `has_capacity` / `try_admit` / `release` / `wait_for_release` plus `current_limit(group)` / `set_limit(group, n)` for live caps; `UnboundedAdmissionGate` / `LimitedAdmissionGate` impls, `ConcurrencyLimits` is the public knob |
| `AdmissionObserver` / `AdmissionEvent` (`admission/`) | interface-base / value-object | hears every admission and release (queue depth, wait, hold, outcome, the gate); attach via `Tapestry(admission_observers=)`. `AdmissionFeedback` (`engine/`) builds the events. **An adaptive concurrency controller is an observer calling `event.gate.set_limit`, not a semaphore of its own.** |

**Idiom:** choose parallelism by swapping a `Dispatcher`, not by changing knots. Agent batch/fleet execution should compose or subclass a dispatcher, not re-implement a bounded-concurrency loop.

**Idiom (resilience):** a per-call timeout or retry is `KnotConfig(timeout=..., retry=KnotRetryPolicy(...))` on the knot, honoured by the engine. A knot that wraps its own body in `wait_for` or a `while True` retry re-implements the engine and loses the attempt count from lineage.

### 3.6 Emitters + Managers — `emitters/`, `managers/`
| Type | Kind | Contract |
|---|---|---|
| `Emitter` (`emitters/base.py`) | interface-base | receives status/lineage events; `log`/`otel`/`kafka`/`valkey`/`webhook` impls; `emitter_error_policy` governs failures |
| `StatusManager` / `StatusEvent` (`managers/`) | engine/value | per-knot lifecycle state + event stream |
| `ExceptionRecord` (`managers/exception_record.py`) | value-object | `ExceptionRecord.for_knot(id, exc)` — the payload inside `Err` |
| `redact` (`managers/redact.py`) | helper | scrubs secrets from emitted records |

**Idiom:** observability is a subscription — implement `Emitter` and attach it; don't thread logging through knot code.

### 3.7 Connectors framework + Capabilities + Backends — `connectors/`, `backends/`
| Type | Kind | Inherits | Contract |
|---|---|---|---|
| `ConnectionConfig` | config | — | credential/DSN config; `dsn_scrubber` redacts for logs |
| `DatabaseConnectionPool` | interface-base | `PirnOpaqueValue` | pooled DB access; `databases/*_pool.py` impls |
| `ObjectStore` | interface-base | `PirnOpaqueValue` | `get/put/delete/list` + shared `_validate_key` (rejects empty/NUL/leading-`/`/`..`) |
| `MessageBroker` | interface-base | `PirnOpaqueValue` | publish/consume; `streaming/*_broker.py` impls |
| `ApiClient` | interface-base | `PirnOpaqueValue` | pooled HTTP client base |
| **`TableSource`** (`capabilities/`) | capability | — | `async fetch_page(cursor, *, page_size) -> (rows, next_cursor)` |
| **`RecordWriter`** (`capabilities/`) | capability | — | `async write_records(records) -> int` |
| `EventEmitter` / `MetadataCatalog` / `MetricQuery` (`capabilities/`) | capability | — | narrow opt-in surfaces connectors implement |
| `DataStore` (`backends/base/`) | interface-base | — | `put/get/has/scrub` by content hash |
| `TapestryStore` (`backends/base/`) | interface-base | — | `register/get/all` knots |
| `RunHistory` / `SubscribableStore` / `TapestrySnapshot` | interface-base | — | run history / pub-sub / point-in-time snapshot |

**Capability pattern (important for agents):** a connector inherits a base (`ObjectStore`) *and* the capabilities it supports (`TableSource`, `RecordWriter`). Consumers depend on the **capability**, so a knot accepting a `TableSource` works over Stripe, Salesforce, or Postgres identically. This is the correct mechanism for optional facets — **not** marker `Protocol`s.

### 3.8 Tapestry + Replay + YAML + Viz — `tapestry.py`, `replay.py`, `yaml_loader/`, `viz/`
| Type | Role |
|---|---|
| `Tapestry` | pipeline container + context manager; knots constructed inside `with Tapestry() as t:` self-register (no `add()` ceremony); `t.run(request)` executes |
| `replay.py` | re-execute from recorded lineage/history |
| `yaml_loader/` | declarative pipelines; `specs/*_spec.py` are the node spec value objects |
| `viz/` | mermaid/html graph rendering |

---

## 4. Canonical idioms

### 4.1 Vending-knot idiom
Bring an externally-constructed resource into the graph as a node with identity + lineage, constructed once per run (the pooling lever). The `process()` is a **bare passthrough**:

```python
class ObjectStoreKnot(Knot):
    def __init__(self, *, store: Knot | ObjectStore, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(store=store, _config=_config, **kwargs)

    async def process(self, store: ObjectStore, **_: Any) -> ObjectStore:
        return store            # NO isinstance guard — validate_io already checked it
```

Usage in a Tapestry (both arms of the `Knot | T` union are real):
```python
with Tapestry() as t:
    store = S3Store(...)                                   # externally constructed
    vend  = ObjectStoreKnot(store=store, _config=KnotConfig(id="s3"))  # scalar → Parameter node
    job   = ExportRows(store=vend, _config=KnotConfig(id="export"))    # vend is a Knot → PARENT
    # ExportRows.process receives the resolved ObjectStore, shared by every consumer of `vend`
```

### 4.2 Capability idiom
Model optional facets as `NotImplementedError` capability base classes a concrete type inherits (like `TableSource`/`RecordWriter`), and have consumers `isinstance`-check the **capability base** (a real subtype check). Do not use marker `Protocol`s + free predicate functions.

### 4.3 Interface idiom
`class X(PirnOpaqueValue): def method(self, ...): raise NotImplementedError(f"{type(self).__name__} must implement method()")`. Inherit `PirnOpaqueValue` iff it holds live/non-pydantic state that crosses the IO boundary.

### 4.4 Outcome idiom
Return/branch on `Ok \| Err \| Skipped`. `Err` carries an `ExceptionRecord`. Never define a parallel `{OK, ERROR, SKIPPED}` status enum. A `process()` that decides not to produce a value **returns `Skipped(reason=...)`** — `Knot.__call__` passes it through bare and the engine records a skip — rather than raising a sentinel or returning `None`; `Optional` alone yields `Ok(Skipped)`.

---

## 5. Decision guide for downstream authors

- **Is it a unit of work in the graph?** → subclass `Knot`, implement `async process(self, ..., **_: Any)`.
- **Is it a live resource (client/pool/driver/model) used as config?** → `NotImplementedError` base class inheriting `PirnOpaqueValue`; concrete impls subclass it; vend via a bare-passthrough knot.
- **Is it an optional facet of a type?** → a capability base class (§4.2), not a `Protocol`.
- **Is it an immutable data shape?** → frozen dataclass, `PirnOpaqueValue` if it carries non-pydantic fields, with `__post_init__` invariants.
- **Does it move values between knots / persist them?** → implement `DataTransport` / `DataStore`, don't hand-roll IO in `process()`.
- **Is it event-driven?** → implement `Trigger` and use `run_forever`, don't hand-roll a consume loop.
- **Is it parallel execution?** → compose a `Dispatcher`, don't re-implement concurrency.
- **Does something succeed/fail/skip?** → `Ok \| Err \| Skipped`, not a new enum.
- **Is it pure logic with no state?** → a plain class with methods; a module-level function only for a genuine decorator or a true "only-way" adapter.

---

## 6. Where pirn-agents currently diverges

Tracked in Linear project **"pirn-agents: OOP/SOLID Standards Remediation"** (PIR-669…726). A full two-pass sweep found agents drifts at two levels: **(A)** OOP/SOLID surface, and **(B)** it *bypasses the execution framework itself*. Headlines mapped to this reference:

**A — surface (WS1–WS6):**
- **§4.4 violated:** `Ok\|Err\|Skipped` unused; parallel `ToolStatus`/`BatchItemStatus` enums. → WS3·S1.
- **§4.1 violated:** vending knots hand-roll `isinstance`/`TypeError` (§1.2) in `process()`. → WS3·S6.

**B — framework bypass (WS7–WS8), the larger finding:**
- **§3.2 ignored (CRITICAL):** control flow (loops, fan-out, routing, gating, map-reduce) is hand-rolled in Python inside knot bodies; `LoopSubTapestry`/`Branch`/`Gate`/`Reduce`/`Aggregator`/`Map` have **zero** real usages — so `Result`/`Skipped`/run-history/determinism/lineage don't cover agent internals. → WS7.
- **§3.5 ignored:** no `Dispatcher` is ever wired; inner `Tapestry()`s default to `LocalDispatcher`; `MapAgent` can't reach Ray/Dask/Thread. → WS7·S7.
- **§3.7 ignored:** connectors don't use `TableSource`/`RecordWriter`; `ConnectorBase`/`HttpConnector` reinvent `ApiClient`. → WS8·S3.
- **§3.7 (backends) ignored:** four parallel KV stores reinvent `DataStore`; determinism reinvents `RunHistory`; no durable backends. → WS8·S1/S2.
- **§3.6 reinvented:** the `observability/` Span plane forks `Emitter`/`OpenTelemetryEmitter`/`LogEmitter` and carries no `run_id`/`knot_id`, so agent spans can't correlate to core lineage. *Resolved by ADR agents-speaks-core WS4a — see below.*
- **§3.6 (managers) unwired:** the secret-redaction layer is built but never attached to `ExceptionManager.traceback_filter`/loggers; approvals ignore `IdentityResolver`. → WS8·S6.

*Resolved since the sweep (do not re-open):*
- **§3.5 / §4.4 (ADR agents-speaks-core, WS0)** — core owns per-knot timeout and retry: `KnotConfig.timeout` → `Err(KnotTimeoutError)`, `KnotConfig.retry: KnotRetryPolicy` run by `GovernedDispatch`, attempts in lineage. Agents' `llm/retry_policy.py::RetryPolicy` and `exceptions/tool_timeout_error.py::ToolTimeoutError` are now shadows to migrate (ratchet: `tests/core_seams/test_core_seam_shadows.py`). Named `KnotRetryPolicy` because the registry keys every class by bare name and agents' `RetryPolicy` already holds `retrypolicy`.
- **§3.1 nested runs (WS0)** — core owns the nested-run depth and cycle guard: `RunNesting` on every run, `Tapestry(max_nesting_depth=)`, inherited and only tightened by inner tapestries; `run_path` now really is `/{outer}/{inner}`. Agents' `AgentNestingConfig` / `AgentToolContext` / `AgentInvoker` and the `AgentRecursionError` family are shadows to migrate.
- **§1.1 declared input schema (WS0)** — `KnotFactory.from_schema` / `@knot(input_schema=)` + `Knot._input_schema_override` validate schema-declared inputs through the standard adapters; `Knot.input_json_schema()` is the signature→schema direction. Agents' `ToolSchemaCompiler`, `ArgumentValidator` and `AgentSchemaDeriver` are shadows to migrate.
- **§3.5 admission feedback (WS0)** — `AdmissionGate.set_limit` / `current_limit` and the `AdmissionObserver` + `AdmissionEvent` seam give an adaptive controller everything it needs from core. Agents' `AdaptiveConcurrencyController`, `ConcurrencyConfig`, `BackpressureSemaphore`, `Bulkhead(Config)`, `AsyncFanoutEngine`, `_FanoutRunner` and `BatchScheduler` are shadows to migrate.
- **§3.2 Check role (WS0)** — `Check(Knot)` names the boolean-verdict role and `Gate(check=)` consumes it directly; `Gate` stays single-input by design (join with `Aggregator`; a `Check` may read several parents). Agents' `GatedAgentResponse` join is a shadow to migrate where the verdict can be a `Check`.
- **§3.2 awaitable loop step (WS0)** — `LoopSubTapestry.astep` / `afold`; the sync pair still works. Resolves the core half of the `ParallelToolExecutor` deferral (agents' backoff-between-attempts loop can now be an `AgentLoopPipeline` iteration).
- **§4.4 bare `Skipped` (WS0, PIR-856 deferral #5)** — a `process()` may return `Skipped`; `Knot.__call__` passes it through, `Gate` / `BranchOutput` do so instead of raising private sentinels (`_GateClosedError` / `_BranchNotSelectedError` deleted), and `Optional` keeps `Ok(Skipped)` via an explicit branch so its lineage contract is unchanged.
- **PIR-849** — `Knot.__call__`, the fan-out path and `SubTapestry.__call__` let a *task* cancellation propagate (`Knot._is_task_cancellation`, `Task.cancelling()`), while a knot raising `CancelledError` itself is still an `Err`. A cancelled run raises; `wait_for` around a knot raises `TimeoutError`.
- **§2** — no `typing.Protocol` interface survives in agents; the stateful ones (`VectorBackendClient`, `GraphBackendClient`, `RerankerBackend`, `NodeEmbeddingIndex`) are `PirnOpaqueValue` bases raising `NotImplementedError`. (WS1)
- **§4.2** — `StatefulTool`/`StreamingTool`/`PermissionedTool` are gone; `stateful`/`state`, `permissions`/`requires_approval` and `streaming`/`stream`/`collect_stream` are default-returning capability members on `Tool`. (WS2·S6)
- **§3.7** — agents' `BlobStore` is gone; `StreamingS3Store` and `ObjectStoreSourceConnector` build on core's `ObjectStore`, keeping `_validate_key`. (WS3·S2)
- **§3.3** — `BatchTrigger` is deleted, `IntervalTrigger` delegates to `CronTrigger` with no schedule loop of its own, `EventTrigger` subclasses core `Trigger`, and `TriggeredBatch` adopts `run_forever`'s ownership and cancellation semantics. (WS8·S4)
- **§3.6 — ADR agents-speaks-core WS4a:** the second event bus is collapsed. `StatusEvent` gained a typed `extra: dict[str, Any]` field (core touch, `pirn/managers/status_event.py`); `pirn.tapestry` gained public `current_emitters()`/`current_emitter_error_policy()` accessors (mirroring `current_run_id()`); `EmitterFanout.emit_status` (core touch, `pirn/engine/emitter_fanout.py`) fans an ad hoc `StatusEvent` out to a run's emitters from inside an async `process()`. `OpenTelemetryEmitter.on_status`/`LogEmitter.on_status` (core touch) now render a non-empty `extra` as, respectively, a `"<kind>:<knot_id>"` span with `agents.<key>` attributes and a `pirn_extra` log field. Agents' `AgentCallRecorder` (`pirn_agents/observability/agent_call_recorder.py`) is the one call LLM/tool/retrieval call sites use; `ToolInvocation` already calls it for every engine-scheduled tool call. `Tracer`/`Span`/`SpanKind`/`SpanStatus`/`OpenSpanEntry`/`ObservabilitySink`/`OtelSink`/`LoggingSink`/`SpanEmittingToolInvocationHook` are one-cycle deprecated shims (`DeprecationWarning` on construction) that still forward into `AgentCallRecorder`, then scheduled for deletion.
- **§3.8 (yaml_loader)** — the builder's `AgentPatternRegistry` (65 pattern names) used to be a table disjoint from the `sweet_tea` registry `PipelineLoader._resolve_callable` reads; every name is now aliased into that same registry at `pirn_agents` import time (`AgentPatternRegistry.register_with_core_registry`), so a core YAML document's `callable: react` resolves exactly like `.pattern("react")` does. `AgentSpec` (the builder's declarative form) is now a projection of core's `PipelineSpec` (`to_pipeline_spec`/`from_pipeline_spec`), and `AgentSpecLoader` accepts a core pipeline document directly, deprecating the old flat-dict-only dialect one cycle. `AgentBuilder.build()`'s runtime seed is bound as a named core `Parameter` (rebindable from `RunRequest.parameters`) instead of a baked constructor kwarg. See `examples/agents_core_pipeline/` for `tapestry-check` validating an agent pipeline written entirely in core's YAML vocabulary. (ADR "agents speaks core" WS6a — `agents-vocabulary-drift-20260913.md`'s "Addendum — authoring surfaces")

*ADR "agents speaks core" WS2 (2026-09-13, exceptions/serialization/batch-outcome/caching/security lanes):*
- **Error roots** — 8 of the 18 agents exception roots the ADR review found now subclass `pirn.exceptions.pirn_error.PirnError` in addition to their existing builtin base (`ToolInvocationError`, `AgentRecursionError`, `SandboxDisabledError`, `UnsupportedModalityError`, `MissingCassetteEntryError`, and `security/`'s `InjectionDetectedError`/`McpTrustError`/`UntrustedDirectiveError`). The other 10 (`llm/`, `mcp/`, `prompt/`, `performance/`, `resilience/`, `memory/`, `specializations/`) are frozen in `tests/test_core_vocabulary_ratchet.py` for their own lanes.
- **§4.4 partially addressed** — `BatchItemResult` gained `to_result()`/`from_result()` bridges to `Ok\|Err\|Skipped`; `BatchItemStatus` itself is not deleted (`MapAgent` scheduling still owns it) and remains listed alongside `ToolStatus`/`FailoverOutcome`/`RetryClassification`/`SpanStatus` in the same ratchet.
- **Hashing — deferred, not a §4 fix yet:** `CanonicalJson.digest`/`encode` still compute their own bare-hex form rather than delegating to `pirn.core.hashing.content_hash`. Three of its seven call sites (`resilience/idempotency_key_assigner.py`, `builder/agent_knot_id_factory.py`, `sessions/run_checkpoint.py`) persist or transmit that digest as a durable/dedup key with no migration path yet, so swapping the algorithm here would silently move those keys. `caching/content_address.py` is not migrated either, for a different reason: `content_hash`'s best-effort opaque-value fallback (a type-only sentinel, never raising) would reopen the exact PIR-785 cache-collision bug `ContentAddress` exists to prevent. Both are documented as open decisions in the WS2 report, not silently dropped.
- **§3.6 (managers) partially wired** — `SecretRedactor.default_traceback_filter()` now returns a `Callable[[str], str]` in the exact shape `Tapestry`/`ExceptionManager.traceback_filter` expects, and `SecretRedactingLogFilter.install()` attaches (idempotently, opt-in) to the package logger. Actually passing `traceback_filter=SecretRedactor.default_traceback_filter()` into the `Tapestry(...)` agents constructs (the pattern registry / builder, `AgentPipeline`'s outer run) is left to WS1/WS6 — this lane does not edit `builder/**` or `specializations/**`.

*Correctly reused (preserve):* `SubTapestry`/`Source`, `PirnOpaqueValue` value objects, `DsnScrubber` composition, HITL suspend/resume (rightly avoids a `Trigger` loop), and raise-site exceptions kept orthogonal to `ExceptionRecord`.

*Resolved by the "agents speaks core" ADR (2026-09-13, separate from the WS1–WS9 remediation project above — its own workstreams are tagged "ADR WS<n>" to avoid confusion with WS1–WS9):*
- **§3.7 (backends), memory half — ADR WS3:** `MemoryRecord` is now a `Payload[MemoryProvenance, MemoryContent]` (§1.3); a writer knot returns it and the engine content-addresses it into `DataStore` like any other knot output, with no separate keyed write. New `MemoryLineageRecall` knot reads it back via `RunHistory.query_lineage_by_knot_id` + `DataStore.get` — the first `pirn_agents` knot to consume `RunHistory`/`DataStore` directly. `MemoryStore` gained a `retention` capability mirroring `DataStore.retention`/`RunHistory.retention` (§3.7), so eviction is one capability instead of a fourth mechanism; `MemoryEvictor`/`LowValueEvictionPolicy` stay as the explicit scored-eviction knot for a held batch. Still open (deferred, needs a product decision — see the ADR WS3 report in `.prompticorn/sessions/`): sessions (`RunState`/`RunCheckpoint`/`SessionStore` → `RunResult`/`RunHistory`) and determinism (`Cassette*`/`TrajectoryRecorder` → `ReplaySession` adapters).
**ADR "agents speaks core" (2026-09-13, superseding-in-progress successor to the sweep above; workstreams named WS0…WS6, distinct from the WS1…WS9 numbering above) — WS5a (control-flow vocabulary) progress:**
- `ResolvedValueKnot`/`MessagesPassthrough`'s constant-seed use → `core/parameter.py`'s `Parameter` (16 call sites across 12 files migrated; both classes kept as one-cycle deprecation shims).

**WS5b (control-flow vocabulary, part 2) progress:**
- The WS5a "no runtime `DeprecationWarning` is possible for a Knot-shaped class" gap is closed: `Knot._deprecated_since: ClassVar[str | None]` (core touch, `pirn/core/knot.py`) plus `Knot._deprecation_notice(self, parents, config_values)` (overridable per-class for a shim deprecated on only one of its call shapes) live in `Knot._bootstrap` — the seam both the standard `Knot.__init__` introspection and a framework primitive that bypasses it (`Parameter`) converge on, so a `Parameter` subclass like `ResolvedValueKnot` is covered too, not only a plain `Knot` subclass. `ResolvedValueKnot` (unconditional) and `MessagesPassthrough` (conditional — warns only for the constant-seed call shape, silent for a genuine upstream `Knot`) now raise `DeprecationWarning` on construction. Documented in `docs/contributing/knot-design-rules.md` Rule 1. Seven-package gate run for this core change.
- `RoundRobinReview` and `RetryOnParseFailure`'s hand-rolled Python loops → `LoopSubTapestry` (`_RoundRobinLoop`, `_RetryOnParseFailureLoop`); 10 of the 12 inventoried imperative loops remain (self_ask, prompt_chain, plan_react, reflexion, lats, flare, multi_hop, json/yaml/pydantic extractors, orchestrator_agent, constitutional_filter, `_raptor_assembler`) — genuinely heterogeneous shapes, not a single mechanical pattern; see the WS5a report's Deferred section.
- `MajorityVoteStrategy` → folds through core `Reduce` instead of a bespoke `ConsensusMajorityVotePicker` knot.
- `pirn_agents.resilience.FailoverAttempt` → `Result` (`Ok\|Err\|Skipped`) per candidate, replacing the parallel `FailoverOutcome` enum + `error: str` pair (§4.4).
- New: `Router.as_branch()` (`interfaces/router.py`) wires a route decision through a real core `Branch` + `Aggregator` fan-in instead of a Python `if route == ...`; ships with a documented laziness caveat (every arm still executes; see the method's docstring) rather than a false claim of full parity with the Python-`if` shape it replaces.
- Not resolved by WS5a: `_AttemptTier`/`_CandidateAttempt`'s fold-accumulator chains (verified — not a pointless `Aggregator` duplicate: `Aggregator` has no partial-success mode under any error policy that also fits a chain whose next step depends on the previous step's resolved outcome); `ConsensusAggregator`'s name (not a core `Aggregator`; rename touches `builder/agent_pattern_registry.py`, a different lane).

---

## 7. The core / agents boundary

**Principle.** The agents layer adds LLM-interaction concepts core deliberately lacks — tools, tool-calling, agent patterns, prompt composition — but **composes them from core primitives** rather than re-implementing execution, outcomes, schema, or persistence.

**What belongs where:**
- **Core** — the dataflow engine: `Knot`, `Result` (`Ok\|Err\|Skipped`), `Tapestry`, transports, triggers, nodes, dispatchers, connectors + capabilities, backend stores, and emitters. Provider-neutral; no LLM-orchestration semantics — core does not even own the model-wire provider contracts.
- **Agents (and sibling domains)** — the LLM-interaction layer: the `LLMProvider`/`EmbeddingProvider` model-wire contracts (each consuming domain owns its own copy — `pirn_agents.llm_provider`/`pirn_agents.embedding_provider`, `pirn_health.llm_provider`, `pirn_ml.embedding_provider`), `Tool`/`ToolCall`/`ToolResult`, agent patterns (RAG/ReAct/plan-execute/…), prompt composition, the tool-calling loop, agent-as-tool.

**Canonical case — the Tool.** A `Tool` is correctly agents-layer (core has no notion of a name + NL description + JSON schema *for a model*). But it must be **composed from** core, and today it is not:
- `Tool.invoke(arguments)` is a **second execution primitive parallel to `Knot.process()`**, called directly by hand-rolled executors (`ParallelToolExecutor`, `planning/tool_executor`) → tool calls run **outside the engine** (no `Result`, lineage, determinism, or caching per call).
- `ToolResult` is a parallel outcome type instead of `Ok\|Err\|Skipped`; `parameters_schema` is a parallel compiler instead of core's signature→`TypeAdapter` introspection. (`Tool(PirnOpaqueValue)` is already correct.)
- **Fix:** a tool invocation should *be or produce* a `Knot`. That single change makes tool-call determinism/record-replay fall out of the engine's `RunHistory` for free — collapsing three reinventions (tool execution, `ToolResult`, and the `determinism/` cassette stack) onto core. Tracked in WS9·S4.

**Rule of thumb.** A new agents abstraction is legitimate when it *names an LLM-interaction concept core lacks*. It is a smell when it *re-implements execution, outcomes, schema, persistence, or concurrency* core already provides — model those the way core does (a `NotImplementedError` base whose execution is a `Knot`). Ratifying this boundary is WS0's core deliverable.

**Core seam gap found by ADR WS3 (candidate WS0 addition).** Neither `DataStore` (`backends/base/data_store.py`) nor `RunHistory` (`backends/base/run_history.py`) mixes in `PirnOpaqueValue` (§1.3), so no `Knot.process()` can declare either as a typed parameter — `Knot._build_adapters` calls `TypeAdapter(ann)` unconditionally for every declared, non-`Knot` parameter, which raises `PydanticSchemaGenerationError` for a type with no pydantic-core schema. `pirn_agents.memory.memory_lineage_recall.MemoryLineageRecall` is the first knot anywhere in the tree to want either as an input (to query lineage and read the `DataStore` recall depends on); it works around the gap by typing both `Any` and checking `isinstance` by hand. The correct fix is likely in core: mix `PirnOpaqueValue` into `DataStore` and `RunHistory` the way every other live-resource base (`ConnectorBase`, LLM/embedding providers) already does, which needs the standard seven-package gate since both are core interfaces every backend subclasses.

---

*Generated from a full read of `packages/pirn-core/pirn`. Keep this in sync when core's base classes change.*
