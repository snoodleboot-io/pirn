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
| `KnotConfig` | config | — | `id` (required), `validate_io`, `error_policy`, `transport` |
| `RunRequest` / `RunResult` / `RunContext` | value-object | — | a run's input/output/ambient context |
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
| `SubTapestry` / `LoopSubTapestry` | nest a tapestry as a node / iterate it |
| `Branch` (`branch/`) | conditional path selection; `BranchOutput` |
| `Gate` (`gate/`) | pass/close predicate gate |
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
| `Shed` / `Edge` (`shed/`) | engine | the resolved execution graph the engine walks |

**Idiom:** choose parallelism by swapping a `Dispatcher`, not by changing knots. Agent batch/fleet execution should compose or subclass a dispatcher, not re-implement a bounded-concurrency loop.

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
Return/branch on `Ok \| Err \| Skipped`. `Err` carries an `ExceptionRecord`. Never define a parallel `{OK, ERROR, SKIPPED}` status enum.

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
- **§2 violated:** 8–9 interfaces are `typing.Protocol` (should be `NotImplementedError` bases); the stateful ones skip §1.3 `PirnOpaqueValue` (vector/graph backend clients, reranker, embedding index). → WS1.
- **§4.2 violated:** `StatefulTool`/`StreamingTool`/`PermissionedTool` are marker `Protocol`s + free functions instead of capability bases/methods on `Tool`. → WS2·S6.
- **§4.4 violated:** `Ok\|Err\|Skipped` unused; parallel `ToolStatus`/`BatchItemStatus` enums. → WS3·S1.
- **§4.1 violated:** 4/9 vending knots hand-roll `isinstance`/`TypeError` (§1.2). → WS3·S6.
- **§3.7 under-reused:** agents' `BlobStore` reinvents `ObjectStore` (drops `_validate_key`). → WS3·S2.

**B — framework bypass (WS7–WS8), the larger finding:**
- **§3.2 ignored (CRITICAL):** control flow (loops, fan-out, routing, gating, map-reduce) is hand-rolled in Python inside knot bodies; `LoopSubTapestry`/`Branch`/`Gate`/`Reduce`/`Aggregator`/`Map` have **zero** real usages — so `Result`/`Skipped`/run-history/determinism/lineage don't cover agent internals. → WS7.
- **§3.5 ignored:** no `Dispatcher` is ever wired; inner `Tapestry()`s default to `LocalDispatcher`; `MapAgent` can't reach Ray/Dask/Thread. → WS7·S7.
- **§3.7 ignored:** connectors don't use `TableSource`/`RecordWriter`; `ConnectorBase`/`HttpConnector` reinvent `ApiClient`. → WS8·S3.
- **§3.7 (backends) ignored:** four parallel KV stores reinvent `DataStore`; determinism reinvents `RunHistory`; no durable backends. → WS8·S1/S2.
- **§3.3 reinvented:** `BatchTrigger`/`IntervalTrigger`/`EventTrigger` clone `Trigger`/`CronTrigger`/`WebhookTrigger` + `run_forever`. → WS8·S4.
- **§3.6 reinvented:** the `observability/` Span plane forks `Emitter`/`OpenTelemetryEmitter`/`LogEmitter` and carries no `run_id`/`knot_id`, so agent spans can't correlate to core lineage. → WS8·S5.
- **§3.6 (managers) unwired:** the secret-redaction layer is built but never attached to `ExceptionManager.traceback_filter`/loggers; approvals ignore `IdentityResolver`. → WS8·S6.

*Correctly reused (preserve):* `SubTapestry`/`Source`, `PirnOpaqueValue` value objects, `DsnScrubber` composition, HITL suspend/resume (rightly avoids a `Trigger` loop), and raise-site exceptions kept orthogonal to `ExceptionRecord`.

---

## 7. The core / agents boundary

**Principle.** The agents layer adds LLM-interaction concepts core deliberately lacks — tools, tool-calling, agent patterns, prompt composition — but **composes them from core primitives** rather than re-implementing execution, outcomes, schema, or persistence.

**What belongs where:**
- **Core** — the dataflow engine: `Knot`, `Result` (`Ok\|Err\|Skipped`), `Tapestry`, transports, triggers, nodes, dispatchers, connectors + capabilities, backend stores, emitters, and `LLMProvider`/`EmbeddingProvider` (the wire to a model). Provider-neutral; no LLM-orchestration semantics.
- **Agents** — the LLM-interaction layer: `Tool`/`ToolCall`/`ToolResult`, agent patterns (RAG/ReAct/plan-execute/…), prompt composition, the tool-calling loop, agent-as-tool.

**Canonical case — the Tool.** A `Tool` is correctly agents-layer (core has no notion of a name + NL description + JSON schema *for a model*). But it must be **composed from** core, and today it is not:
- `Tool.invoke(arguments)` is a **second execution primitive parallel to `Knot.process()`**, called directly by hand-rolled executors (`ParallelToolExecutor`, `planning/tool_executor`) → tool calls run **outside the engine** (no `Result`, lineage, determinism, or caching per call).
- `ToolResult` is a parallel outcome type instead of `Ok\|Err\|Skipped`; `parameters_schema` is a parallel compiler instead of core's signature→`TypeAdapter` introspection. (`Tool(PirnOpaqueValue)` is already correct.)
- **Fix:** a tool invocation should *be or produce* a `Knot`. That single change makes tool-call determinism/record-replay fall out of the engine's `RunHistory` for free — collapsing three reinventions (tool execution, `ToolResult`, and the `determinism/` cassette stack) onto core. Tracked in WS9·S4.

**Rule of thumb.** A new agents abstraction is legitimate when it *names an LLM-interaction concept core lacks*. It is a smell when it *re-implements execution, outcomes, schema, persistence, or concurrency* core already provides — model those the way core does (a `NotImplementedError` base whose execution is a `Knot`). Ratifying this boundary is WS0's core deliverable.

---

*Generated from a full read of `packages/pirn-core/pirn`. Keep this in sync when core's base classes change.*
