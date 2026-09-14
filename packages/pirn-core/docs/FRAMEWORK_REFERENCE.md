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

**A schema can stand in for the signature.** `KnotFactory.from_schema(name, input_schema, process)` / `@KnotFactory.knot(input_schema=...)` declare the inputs of a knot that has no Python signature (an MCP-declared tool) with a JSON object schema; `Knot._input_schema_override` carries it and `JsonSchemaTypeBuilder` turns each property into the `TypeAdapter` `validate_io` applies. The inverse, `Knot.input_json_schema()`, renders any knot's hinted inputs as the same kind of schema — the source for model-facing declarations.

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
- Docstrings sometimes say "protocol" informally (e.g. `triggers/trigger.py`) — the *code* is always a `NotImplementedError` base class.
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
| `KnotFactory` / `@KnotFactory.knot` | factory | — | `core/knot_factory.py` — a function's signature becomes a Knot's input contract; `from_schema(name, input_schema, process)` / `@KnotFactory.knot(input_schema=)` do the same from a JSON object schema |
| `JsonSchemaTypeBuilder` | helper | — | `core/json_schema_type_builder.py` — JSON-schema fragment → Python type for `TypeAdapter` (scalars, enum/const, nullable, anyOf/oneOf, arrays, objects as `TypedDict`, local `$ref`, bounds). **Do not write a second schema→validator or signature→schema compiler.** |
| `KnotConfig` | config | — | `id` (required), `validate_io`, `error_policy`, `transport`, `concurrency_group`, `timeout`, `retry` |
| `KnotRetryPolicy` | value-object | — | `core/knot_retry_policy.py` — frozen backoff schedule (`max_attempts`, `base_delay`, `max_delay`, `multiplier`, `jitter`, `max_retry_after`) plus `is_retryable` / `retry_after` predicates over the failed attempt's `ExceptionRecord`. Set on `KnotConfig.retry`; the **engine** runs the loop (§3.5). `run(attempt, *, retry_on=, retry_after_hint=, sleep=, rng=)` drives the same schedule for a call *below* the knot boundary (an HTTP POST, an embedding batch, a reconnect). **Do not write a retry loop inside a knot, or a second backoff implementation anywhere.** |
| `RunRequest` / `RunResult` / `RunContext` | value-object | — | a run's input/output/ambient context; `RunContext.nesting` is the run's `RunNesting` frame |
| `RunNesting` | value-object | — | `core/run_nesting.py` — where a run sits in the nested-run tree (`depth`, enclosing `run_ids`, container `path`, tightest `max_depth`); `RunNesting.current()` inside a knot. `Tapestry(max_nesting_depth=n)` turns the guard on: `NestingDepthExceededError` / `NestedRunCycleError` as the container knot's `Err`. **Do not carry a recursion counter through agent code.** |
| `ErrorPolicy` | enum/policy | — | how upstream `Err` propagates (`RECEIVE_ERRORS` etc.) |
| `IdentityResolver` | interface-base | — | `core/identity/` — `resolve()` who's running; `chained/env/os/static/null` implementations |
| `ContentHasher.hash(value, *, strict=False)` | static method | — | `core/content_hasher.py` — the one content-addressing seam (`sha256:`-prefixed). Default is best-effort: an opaque leaf degrades to a `sha256:unhashable:<type>` sentinel. `strict=True` raises `UnhashableValueError` (`PirnError, TypeError`) naming the innermost offending type instead — for a caller (a cache key, a dedup key) where the sentinel's silent collision risk is unacceptable, not just an inconvenience. (ADR agents-speaks-core WS2 part 2) |

### 3.2 Nodes — `nodes/`
All subclass `Knot`. These are the graph-shape primitives.
| Type | Role |
|---|---|
| `Source` / `Sink` | graph entry / exit |
| `Aggregator` | fan-in of multiple parents |
| `Reduce` | fold over a collection |
| `Continuation` | deferred/streaming continuation |
| `NestedRunKnot` (`nested_run_knot.py`) | a plain knot whose `process()` runs nested tapestries through `self._run_inner(inner)` and returns its own value — any number of inner runs, no sink contract. Each inner run inherits the enclosing run's observability/value plane (history, emitters, data store, transport, traceback filter) and execution plane (dispatcher, gate + limits, observers, replay, identity), nests under its `RunNesting` frame, and is recorded on the knot's row (`extra["inner_run_id"]`, plus `extra["inner_run_ids"]` in start order when there are several — what an inherited replay posture picks the matching recording by). A container: holds no admission slot, may not carry a `concurrency_group`. Mix it in beside a marker base (`class X(Assembler, NestedRunKnot)`) — `_raptor_assembler` is the reference use (PIR-872). **Use this, not a `SubTapestry` whose `__call__` is overridden back, when a knot needs inner runs but returns a value.** |
| `SubTapestry` / `LoopSubTapestry` | a `NestedRunKnot` with the sink contract: `process()` returns the terminal knot of one inner pipeline and its output becomes the knot's; the loop iterates it, its `astep` / `afold` are awaited (override them, or declare `step`/`fold` as `async def`) so an iteration can sleep, check a budget or call a model between turns |
| `Branch` (`branch/`) | conditional path selection; `BranchOutput` |
| `Gate` (`gate/`) | pass/close gate; decision is `predicate=` (callable) or `check=` (a `Check` knot). Closed, it records `"gate_closed"` — or the check's `skip_reason`, propagated to every knot it skips (`Skipped.propagates`, PIR-872) |
| `Check` (`check.py`) | the predicate half of a `Gate`: any parents → `bool`, enforced; `skip_reason` names why a `False` verdict stopped the graph, in lineage. **The core name for a boolean verdict knot; agents' `*Check` knots subclass it, not `Knot`.** |
| `Map` / `ZipMap` / `DictMap` (`map_markers.py`) | fan-out markers on a `process()` input → per-element execution |

**Idiom:** distribution is declarative — annotate an input with a `Map`/`ZipMap`/`DictMap` marker and the framework runs `process()` once per element (`Knot._fan_out`).

### 3.3 Triggers + Streaming — `triggers/`, `streaming/`
| Type | Kind | Contract |
|---|---|---|
| `Trigger` | interface-base | `name` (prop), `stream() -> AsyncIterator[RunRequest]`, `async close()` — all raise `NotImplementedError` |
| `Cron` / `Http` / `Kafka` / `Valkey` triggers | concrete | async generators yielding one `RunRequest` per event |
| `Trigger.run_forever(self, tapestry, *, on_result, on_error)` | driver method | pulls requests, calls `tapestry.run` per event, `close()`s on exit |
| `StreamingSource` (`streaming/streaming_source.py`) | interface-base | streaming input adapters; `trigger_adapter.py` bridges a stream to the trigger loop |

**Idiom (the trigger loop):** a `Trigger` is an async generator of `RunRequest`s; `Trigger.run_forever` is the runtime that consumes them and runs the tapestry. Downstream event-driven agents should implement `Trigger`, not hand-roll a consume loop.

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
| `Admission` (`admission/`) | interface-base | `has_capacity` / `try_admit` / `release` / `wait_for_release` plus `current_limit(group)` / `set_limit(group, n)` for live caps; `UnboundedAdmission` / `LimitedAdmission` impls, `ConcurrencyLimits` is the public knob |
| `AdmissionObserver` / `AdmissionEvent` (`admission/`) | interface-base / value-object | hears every admission and release (queue depth, wait, hold, outcome, the gate); attach via `Tapestry(admission_observers=)`. `AdmissionFeedback` (`engine/`) builds the events. **An adaptive concurrency controller is an observer calling `event.gate.set_limit`, not a semaphore of its own.** |
| `ExecutionPlane` (`core/execution_plane.py`) | value-object | the scheduling half of a run — `dispatcher`, `gate` + `limits`, `admission_observers`, `replay`, `identity_resolver` — published by `Tapestry.run` for the run's duration (`ExecutionPlane.current()`) and **inherited by every inner run** for whatever the inner tapestry did not name: the gate by identity, so `ConcurrencyLimits` are one budget across the run tree. Container knots (`Knot._holds_admission_slot = False`: `SubTapestry`, loop iterations) take no slot and may not carry a `concurrency_group`. Per-container overrides: `NestedRunKnot._run_inner(dispatcher=, concurrency=, admission_observers=)` (inherited by `SubTapestry`) or the `_inner_dispatcher` / `_inner_concurrency` / `_inner_admission_observers` hooks (ADR WS0b) |

**Idiom:** choose parallelism by swapping a `Dispatcher`, not by changing knots. Agent batch/fleet execution should compose or subclass a dispatcher, not re-implement a bounded-concurrency loop. An inner run inherits the outer dispatcher and admission gate; a container that needs its own overrides them through `_run_inner` / the `_inner_*` hooks — **never by assigning an inner tapestry's private fields** (ratcheted in agents' `tests/core_seams/test_execution_plane_reach_through.py`).

**Idiom (resilience):** a per-call timeout or retry is `KnotConfig(timeout=..., retry=KnotRetryPolicy(...))` on the knot, honoured by the engine. A knot that wraps its own body in `wait_for` or a `while True` retry re-implements the engine and loses the attempt count from lineage.

### 3.6 Emitters + Managers — `emitters/`, `managers/`
| Type | Kind | Contract |
|---|---|---|
| `Emitter` (`emitters/emitter.py`) | interface-base | receives status/lineage events; `log`/`otel`/`kafka`/`valkey`/`webhook` impls; `emitter_error_policy` governs failures. **`on_knot_result(knot_id, result, lineage)`** (ADR WS0b) is the live per-knot stream: awaited by the engine the moment a knot settles, with the full `Ok`/`Err`/`Skipped` (the `Err`'s rebound `ExceptionRecord` included) and its lineage row, before the knot's children start — the hook a fan-out consumer streams per-item outcomes from before the join completes. No-op default; same error policy as `on_lineage` |
| `StatusManager` / `StatusEvent` (`managers/`) | engine/value | per-knot lifecycle state + event stream |
| `ExceptionRecord` (`managers/exception_record.py`) | value-object | `ExceptionRecord.for_knot(id, exc)` — the payload inside `Err` |
| `TracebackRedactor` (`managers/traceback_redactor.py`) | helper | scrubs secrets from emitted records |

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
| `RunHistory` / `SubscribableStore` / `TapestrySnapshot` | interface-base | — | run history / pub-sub / point-in-time snapshot. `RunHistory.query_lineage_by_knot_id` lists every row for a knot id; **`query_latest_lineage_by_knot_id(knot_id) -> KnotLineage \| None`** (ADR WS0b) is the single most-recently-finished row (by `finished_at`) — the keyed-identity lookup agents' memory recall / resume-after-crash key on; implemented by the in-memory, SQLite, DuckDB and Postgres stores and pinned by the backend conformance suite |

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
- **Is it event-driven?** → implement `Trigger` and use `Trigger.run_forever`, don't hand-roll a consume loop.
- **Is it parallel execution?** → compose a `Dispatcher`, don't re-implement concurrency.
- **Does something succeed/fail/skip?** → `Ok \| Err \| Skipped`, not a new enum.
- **Is it pure logic with no state?** → a plain class with methods; a module-level function only when it is a documented public entry point on the `scripts/check_conventions.py` allowlist (PIR-869) — a genuine decorator, an ambient accessor or a driver. Anything else is a `@staticmethod`; a replaced name is deleted, never kept as a bare alias (alpha policy, `docs/guides/versioning.md`).

---

## 6. Resolved by ADR agents-speaks-core

Agents drifted from this reference in two ways the original 2026 sweep
(Linear **"pirn-agents: OOP/SOLID Standards Remediation"**, PIR-669…726)
found: **(A)** an OOP/SOLID surface issue (parallel outcome enums, hand-rolled
`isinstance` guards) and **(B)** the larger finding — it *bypassed the
execution framework itself* (hand-rolled loops/fan-out/routing instead of
`LoopSubTapestry`/`Aggregator`/`Branch`, no `Dispatcher` ever wired, four
parallel KV stores reinventing `DataStore`, a second observability plane with
no `run_id`/`knot_id`). The ADR "agents speaks core" (2026-09-13, workstreams
WS0…WS6b) is what actually closed nearly all of it, seam by seam; this
section is organized by subsystem rather than by workstream so a reader can
find "what changed" without reconstructing which PR did it. A replaced name
is deleted outright — pirn is alpha, so nothing is deprecated first
(`docs/guides/versioning.md`) — and `CHANGELOG.md`'s "Removed" / "Renamed"
sections are the authoritative name → replacement table.

### Retry, timeout, and nesting (core seams, WS0)

Core now owns per-knot timeout and retry (`KnotConfig.timeout` →
`Err(KnotTimeoutError)`, `KnotConfig.retry: KnotRetryPolicy` run by
`GovernedDispatch`, attempts recorded in lineage) and the nested-run depth and
cycle guard (`RunNesting` on every run, `Tapestry(max_nesting_depth=)`,
inherited and only tightened by inner tapestries). **Resolved (PIR-872):** agents
carries none of these any more, and every set in
`tests/core_seams/test_core_seam_shadows.py` is a `frozenset()` assertion.

- **Retry.** A knot declares `KnotConfig(retry=KnotRetryPolicy(...))`. A retry
  that is not a knot dispatch — `HttpTransport`'s POST, an embedding batch in
  `BaseEmbeddingProvider`, `McpConnector`'s reconnect, `IdempotentRetryPolicy`'s
  safe-retry — calls `KnotRetryPolicy.run(attempt, retry_on=, retry_after_hint=)`,
  the same `should_retry`/`delay_before_retry` decision `GovernedDispatch`
  makes, over an `ExceptionRecord` built from the live exception. Agents'
  `RetryPolicy` is deleted.
- **Timeout.** `KnotConfig.timeout` → `Err(KnotTimeoutError)`; `ToolTimeoutError`
  is deleted.
- **Nesting.** Depth, enclosing run ids, container path and cap are
  `RunNesting` (`RunNesting.current()`), refused with
  `NestingDepthExceededError`/`NestedRunCycleError`. `AgentRecursionError`,
  `AgentDepthExceededError`, `AgentCycleError`, `AgentToolContext` (with its
  own `child()`/`stack` depth and cycle tracking) and `AgentNestingConfig` are
  deleted; `AgentToolCall` turns its `max_depth=8` agent-as-tool frames into
  `Tapestry(max_nesting_depth=RunNesting.current().depth + 2 * frames)`. What
  core does not own — the shared `RunBudgetMeter` and pooled `LLMProvider` an
  agent-as-tool tree propagates — is `AgentToolPolicy`, a `meter`/`provider`
  carrier with no nesting state.

### Tool — RESOLVED (WS1)

A `Tool` is correctly agents-layer (core has no notion of a name + NL
description + JSON schema *for a model*); it is now **composed from** core
rather than parallel to it. See §7 for the full case — it is the canonical
example of the boundary this ADR draws.

### Outcomes, errors, and hashing (WS2)

`Ok|Err|Skipped` is now the outcome vocabulary agents targets: `BatchItemResult`
gained `to_result()`/`from_result()` bridges; `pirn_agents.resilience.FailoverAttempt`
→ `Result` per candidate, replacing the `FailoverOutcome` enum (deleted, PIR-872; a circuit-open candidate is `Skipped(reason="circuit_open")`, and `RetryClassification` became `RetrySafetyClassifier.is_safe() -> bool`); `ModelCascadeRouter`/
`FallbackChain`/`FailoverChain`'s fold-accumulator chains now run as a
`LoopSubTapestry` (`_CascadeLoop`/`_FallbackLoop`/`FailoverLoop`) that stops
scheduling once the chain locks, rather than a static unrolled chain that
still built a knot per candidate past the lock point. 8 of the 18 agents
exception roots the ADR found now also subclass `pirn.exceptions.pirn_error.PirnError`
(`ToolInvocationError`, `AgentRecursionError`, `SandboxDisabledError`,
`UnsupportedModalityError`, `MissingCassetteEntryError` (since deleted with its recorder, PIR-872), `InjectionDetectedError`,
`McpTrustError`, `UntrustedDirectiveError`); PIR-872 rooted the other nine
(`BudgetBreachError`, `StructuredDecodeError`, `SpecialistInvocationError`,
`ConstitutionalViolationError`, `McpError`, `PromptRenderError`,
`CircuitOpenError`, `LLMProviderError`, `RateLimitSignal`) on `PirnError` too,
keeping each builtin base callers catch, and deleted the orphaned
`KeyIndexUnreadableError`; `tests/test_core_vocabulary_ratchet.py` holds the
inventory at empty. `ContentHasher.hash` (§4.4) is the one
hashing path; `ContentAddress`/`content_address()` are deleted (PIR-864) and
every caller calls `ContentHasher.hash(value, strict=True)` directly.

**Resolved (PIR-872):** `BatchItemStatus` is deleted — `BatchItemResult.outcome` is the
item's core `Result` (`Ok`, `Err` — a timeout is an `Err` whose error type is
`KnotTimeoutError` — or `Skipped(reason="resumed")`). `CanonicalJson`/`OpaquePolicy` are deleted (PIR-872): their last callers
(`determinism/content_digest.py`, `evaluation/trajectory_call_key.py`) call
`ContentHasher.hash(value, strict=True)` directly, like `IdempotencyKeyAssigner` and
`AgentKnotIdFactory` already did.

### Memory, sessions, and determinism (WS3, parts 1-4)

`MemoryRecord` is a `Payload[MemoryProvenance, MemoryContent]` (§1.3); a
writer knot returns it and the engine content-addresses it into `DataStore`
like any other knot output. `MemoryLineageRecall` reads it back via
`RunHistory.query_lineage_by_knot_id` + `DataStore.get`. A caller-chosen key
is now a knot id, not a KV slot: `RunHistory.query_latest_lineage_by_knot_id`
(core touch; base default + efficient overrides in all four shipped stores)
answers "the current value under this key," and `KeyedLineageStore` wraps the
write/read pair; `DataStoreMemoryStore`'s old `content_hash(key)` method
(which hashed the caller's key, not a value) is deleted outright.
`MemoryStore` gained a `retention` capability mirroring `DataStore.retention`/
`RunHistory.retention`, so eviction is one capability instead of a fourth
mechanism.

A session is one engine run per turn linked by `_parent_run_id` (`SessionChain`);
`RunState` is a read-model projected from that chain (`RunState.from_chain`),
not a persisted checkpoint blob. HITL suspend is `Skipped(reason="awaiting_human")`
(the same conversion core's `Gate` uses for `_GateClosedError`); resume
(`ApprovalResumer`) replays the suspended run's recorded prefix via
`ReplaySession(allow_new_knots=True)` (§3.8) — a new core seam letting a knot
with no recorded row run live instead of raising `ReplayMismatchError`. A
determinism fork (`CheckpointForker`) is a branch of the session chain — a
`(run_id, output_hash)` fork point verified against the recording, then a new
run chained via `_parent_run_id` that replays the prefix and executes whatever
diverges. `CassetteRecorder` became a thin adapter over `Tapestry.run()`/
`Tapestry.run(replay=...)` here, and PIR-872 deleted it outright — callers use
`Tapestry.run(replay=...)` directly (an eval: `RunEval.run(replay=...)`); `TrajectoryEmitter` captures every knot's lineage
into a `RunTrace` via `on_lineage`, no manual `.record()` calls. `DataStore`
and `RunHistory` both now mix in `PirnOpaqueValue` (§1.3), closing the gap
that kept `Knot.process()` from declaring either as a typed parameter — WS3's
own `RunResumer`/`ApprovalResumer` are the first to declare them directly.

Deleted (PIR-864): `RunCheckpoint`/`RunCheckpointer`/`SessionStore`/
`InMemorySessionStore`/`PersistedSessionStore`/`ThreadRepository`/
`MemoryStoreKeyIndex`, `CassetteStore`/`InMemoryCassetteStore`/
`FileCassetteStore`/`TrajectoryRecorder`. `TraceDiffer` is a live class and
stays.

### Observability (WS4a)

The second event bus is collapsed: `StatusEvent` gained a typed
`extra: dict[str, Any]` field (core touch); `EmitterFanout.emit_status` (core
touch) fans an ad hoc `StatusEvent` out to a run's emitters from inside an
async `process()`; `OpenTelemetryEmitter`/`LogEmitter` (core touch) render a
non-empty `extra` as span attributes / a log field. `AgentCallRecorder` is now
the one call every LLM/tool/retrieval call site uses. Deleted (PIR-864):
`Tracer`/`Span`/`SpanKind`/`SpanStatus`/`OpenSpanEntry`/`ObservabilitySink`/
`OtelSink`/`LoggingSink`/`SpanEmittingToolInvocationHook` — the entire second
event bus, with zero production call sites outside `observability/` itself
(`tests/test_event_bus_ratchet.py`).

**Partially wired:** `SecretRedactor.default_traceback_filter()` returns a
`Callable[[str], str]` in the exact shape `Tapestry`/`ExceptionManager.traceback_filter`
expects, and `SecretRedactingLogFilter.install()` attaches (idempotently,
opt-in) to the package logger — but actually passing
`traceback_filter=SecretRedactor.default_traceback_filter()` into the
`Tapestry(...)` agents constructs (the pattern registry, the builder,
`AgentPipeline`'s outer run) is not done; `builder/**` and `specializations/**`
are untouched by this wiring.

### Scheduling and concurrency (WS4b, "one scheduler")

`MapAgent` is a `SubTapestry` whose inner graph is one `MapItem` knot per
input item joined by a core `Aggregator` under `ErrorPolicy.RECEIVE_ERRORS`;
concurrency is `KnotConfig(concurrency_group=)` + `ConcurrencyLimits`; per-item
timeout/retry is `KnotConfig.timeout`/`KnotConfig.retry`, run by
`GovernedDispatch`. Resume-after-crash is a `RunHistory.query_lineage_by_knot_id`
lookup on the item's knot id (`item:<batch_id>:<key>`), not an F14 checkpoint
store. `AdaptiveConcurrencyController` is now an `AdmissionObserver` (additive
increase on `on_release`, multiplicative decrease on a new `on_throttle()`
called directly by `MapItem`). `TriggeredBatch`/`IntervalTrigger`/`EventTrigger`
needed no changes — they already composed core `Trigger`.

A caveat this exposed: `SubTapestry`'s inner run does not forward the
enclosing run's dispatcher or concurrency limits through a public seam, so
`MapAgent` reaches into the inner `Tapestry`'s private fields the same way
`SubTapestry._apply_inherited_value_plane` already does for the value plane.
ADR WS0b's `ExecutionPlane` (`core/execution_plane.py`) closed this: it is
published by `Tapestry.run` and inherited by every `SubTapestry` inner run and
`LoopSubTapestry` iteration for whatever the inner tapestry did not name
(dispatcher; admission gate, **the same instance**, so `ConcurrencyLimits` are
one budget across the run tree; admission observers, merged; replay posture;
identity resolver) — `MapAgent` now overrides `_inner_dispatcher`/
`_inner_concurrency`/`_inner_admission_observers` instead of reaching into
private fields (`tests/core_seams/test_execution_plane_reach_through.py`
ratchets the inventory at empty). WS0b also added per-item streaming from a
fan-out (`Emitter.on_knot_result` fires the instant each knot settles, so
`MapAgent.run()`'s `async for` yields incrementally again) and
`RunHistory.query_latest_lineage_by_knot_id`.

Deleted (PIR-864): `BatchCheckpointer`/`BatchScheduler`, `AsyncFanoutEngine`/
`_FanoutRunner` (machinery removed once `MapAgent` moved onto `Map`/`Aggregator`).

PIR-867 moved `document_processing/_ingestion_runner.py` (`IngestionPipeline`'s
internal ETL runner) and `multi_agent/orchestrator_workers.py` off a bare
`asyncio.Semaphore(max_concurrency)` shared across their per-item knots (held
across the real await) onto `KnotConfig(concurrency_group=)` on the per-item
knots + a `ConcurrencyLimits` group cap set via `_inner_concurrency()` — the
same lever `MapAgent` uses — so the bound is the admission gate's own budget,
not a second, private one it cannot see.

`caching/prompt_cache.py::PromptCache` — RESOLVED (PIR-868). Entries now
live in a core `InMemoryDataStore` keyed by content hash, exactly like
`SemanticResultCache`; the prefix/embedding index stays a plain
`SimilarityIndex` resource. `DataStore` is async-only with no enumeration,
so its management surface is async: `ainvalidate`/`apurge_expired`/`asize`.
The synchronous `invalidate`/`purge_expired`/`__len__` bridges are deleted
(PIR-872).

**Resolved (PIR-866), superseded by full deletion (PIR-864).** PIR-866 first
turned `BackpressureSemaphore`/`Bulkhead` into `Admission` subclasses
delegating to a real `LimitedAdmission` through a shared
`pirn_agents.performance._backpressure_admission._BackpressureAdmission` (the
one place `max_queue_depth`/`acquire_timeout` — backpressure knobs core's
`Admission` has no equivalent for outside a running `Tapestry` — were
still implemented directly), and gave `ConcurrencyConfig`/`BulkheadConfig` a
`to_concurrency_limits()` bridge, while documenting a blocker: three
`specializations/` pipelines plus `agent/parallel_tool_executor.py` read
`ConcurrencyConfig.max_concurrency` as a **class-level** literal default
(`max_concurrency: Knot | int = ConcurrencyConfig.max_concurrency`), which a
pydantic `BaseModel` subclass cannot support (no class-level field-default
access; a `@property` returns the descriptor on class access, not its
value), and `evaluation/run_eval.py` ran no `Tapestry` at all (a bare
`asyncio.gather` loop), so it could not adopt a knot-scoped concurrency group
without first being wired onto the engine.

**PIR-864 deleted the entire plane outright** rather than resolve the
blocker: `BackpressureSemaphore`, `Bulkhead`, `ConcurrencyConfig`,
`BulkheadConfig`, and the now-unreferenced `_backpressure_admission`/
`_admission_slot_knot` implementation modules are gone, along with every test
that existed only to exercise them (`tests/performance/test_concurrency_config.py`
including its `TestClassLevelDefaultAccess` pin, `test_backpressure_semaphore.py`,
`test_backpressure_admission.py`, `tests/resilience/test_bulkhead.py`,
`test_bulkhead_config.py`). `agent/parallel_tool_executor.py` and the three
`specializations/` pipelines (`document_processing/ingestion_pipeline.py`,
`multi_agent/orchestrator_workers.py`, `rewoo/rewoo_pipeline.py`) that used
to read the class-level default now default to a plain literal `8`.
`evaluation/run_eval.py::RunEval.run` — then the one caller with no `Tapestry` to
attach a concurrency group to — bounded its per-item concurrency with a plain
`asyncio.Semaphore(concurrency)` for one cycle. **Resolved (PIR-872):** it
now runs on the engine — one `_EvalCase` knot per item (target call, metric
scoring, threshold check) with `KnotConfig(concurrency_group="eval_items")`,
capped by `ConcurrencyLimits(groups={"eval_items": concurrency})`, fanned into
an `Aggregator` that assembles the `EvalReport` in dataset order. Eval
determinism is core replay: `RunEval.run(history=, data_store=, run_id=)`
records each item's result, and `RunEval.run(replay=ReplaySession(...))` serves
it without calling the target (a replay whose items, thresholds, metric names
or target/metric *code* differ raises `ReplayMismatchError` — callables are
identified by bytecode, constants, names, defaults, closure values and bound
arguments via `_CallableIdentity`; only a callable with no inspectable code,
such as a C builtin, falls back to `module.qualname`). The agents recorder seam it
used to route through — `RunRecorder`, `NullRunRecorder`, `CassetteRunRecorder`,
`CassetteRecorder`, `Cassette`/`CassetteEntry`/`InteractionKind`/`RecordingMode`,
`MissingCassetteEntryError` — is deleted; `tests/tools/test_tool_is_a_knot_ratchet.py`'s
`INVOKE_CLASSES` is empty (`ToolTestHarness` drives a call through
`Tapestry.run` instead of an `invoke` method).
`caching/prompt_cache.py::PromptCache` stays outside this migration
entirely: its `get`/`set`/`__len__` are deliberately synchronous, and
`DataStore` is async-only, so routing values through it would force a
breaking signature change this ADR did not authorize unilaterally.

**Resolved (PIR-870), three admission/dispatch refinements noted as future
work above WS0b landed:**
- An inner run naming a *bounded* `ConcurrencyLimits` of its own now gets a
  `ChainedAdmission` — a ticket from both its own gate and the enclosing
  run's, released together — instead of an unrelated gate that let the two
  budgets add rather than compose. An explicitly unbounded
  `ConcurrencyLimits()` is unaffected: it stays the documented opt-out.
- `Dispatcher.dispatcher_for_container(knot)` (default: identity) lets a
  dispatcher route a container knot (`SubTapestry`/`LoopSubTapestry`/a loop
  iteration) somewhere other than itself; `ThreadDispatcher` answers with a
  shared `LocalDispatcher` so a container runs on the event loop instead of
  spending one of its own pool workers on a wait for its inner run's leaves
  — which need that same pool.
- `GovernedDispatch` releases a retrying knot's admission ticket for the
  backoff sleep and re-admits (via a new `AdmissionTicketHolder` the engine
  reads back) before the next attempt, so a sleeping retry no longer holds a
  slot another ready knot could use. `KnotLineage.extra["attempts"]` is
  unchanged.

### Control-flow vocabulary (WS5a, WS5b)

`Check(Knot)` names the boolean-verdict role and `Gate(check=)` consumes it
directly. `LoopSubTapestry.astep`/`afold` give an awaitable loop step.
`ResolvedValueKnot`/`MessagesPassthrough`'s constant-seed use moved onto
`core/parameter.py`'s `Parameter` (16 call sites across 12 files); both
classes are deleted (PIR-864). `ConsensusAggregator` is deleted in favour of
`ConsensusPipeline`. All 12 inventoried imperative
loops are now `LoopSubTapestry`s: `RoundRobinReview`/`RetryOnParseFailure`
(WS5a); `SelfAskPipeline`, `PromptChainPipeline`, `ReflexionPipeline` (its LLM
call gated by a `Check`→`Gate` pair so a successful attempt never pays for
it), `FlareActiveRagPipeline` (the same Check/Gate shape for conditional
retrieval), `JsonExtractorPipeline`/`YamlExtractorPipeline`/
`PydanticValidatorPipeline` (WS5b). `PlanReActPipeline`'s planner call and
`LatsSearch`'s per-expansion proposer call moved from a bare
`await child.process(...)` inside an unrun `Tapestry()` to `self._run_inner(...)`.
`AdaptiveRAGPipeline`'s routing is now a real core `Branch` with an
implicit-dependency gate per arm, so an unselected arm's LLM/retrieval call
never fires — stricter than `Router.as_branch()`'s documented "every arm still
executes" default. `MajorityVoteStrategy` folds through core `Reduce`.
`_LLMCallKnot`/`LLMChatCall`/`MemorySearchRetriever` report through
`AgentCallRecorder` like `ToolInvocation` already did.

`retrieval/graph_rag/hybrid_graph_retriever.py::HybridGraphRetriever`'s
`traversal: GraphTraversal` parameter used to be a bare `Knot` subclass named
as a *value* type on `process()`, which made `Knot._build_adapters` raise the
moment the class was constructed through its real `__init__` — so it awaited
the traversal knot's `process()` directly instead (`AWAITS_CHILD_PROCESS`).
Fixed in PIR-867: `GraphTraversal` is wired as a genuine upstream parent, with
its own `store`/`budget`/`start_ids`/`direction`/`edge_types` bound at its own
construction; `HybridGraphRetriever.process()` receives the traversal's
resolved `Subgraph` like any other parent's output.

Three more `LOOP_AWAITS_LLM_OR_TOOL_CALL` sites fixed in PIR-867:
`ChunkTranslator` (`specializations/document_processing/`) and
`FactClaimVerifier` (`specializations/guardrails/`) translate/verify
independent items — chunk N's translation and claim N's search never depend
on item N-1's outcome — so each now fans out one per-item knot
(`ChunkTranslation` / `_ClaimVerification`) into an `Aggregator`, in the
`ParallelToolCaller` style, instead of awaiting `llm.chat`/`store.search` in a
hand-rolled `for` loop. `PlanExecutor` (`specializations/plan_and_execute/`)
is different: step N's prompt genuinely includes every prior step's result,
so it wires a `LoopSubTapestry` (`PlanStepLoop`) instead — the state
threaded across iterations is the running tuple of step results.

Three more `USES_ASYNCIO_GATHER` sites fixed in PIR-867: `HybridRetriever`
(`retrieval/`) now wires its dense and lexical arms as two knots
(`DenseIds`/`LexicalIds`, the BM25 side still offloading to a worker thread
internally via `asyncio.to_thread`) into an `Aggregator`, so it is a
`SubTapestry` now rather than a plain `Knot` — `HybridRetrieverBase` stays a
plain `Retriever`/`Knot` base since `HybridGraphRetriever` still needs that
shape, so `HybridRetriever` picks up `SubTapestry` itself
(`class HybridRetriever(SubTapestry, HybridRetrieverBase)`).
`ChunkEmbedderStore` (`specializations/document_processing/`) wires one
`ChunkStoreWrite` per chunk into an `Aggregator` (the batched embedding call
itself stays a single call — batching is the reason the embedder gets every
chunk at once). `IngestionRunner` (`specializations/document_processing/`)
wires one `DocumentIngest` per source document into an `Aggregator`, with a
`ConcurrencyLimits` group cap set via the `_inner_concurrency()` hook
(`MapAgent`'s own lever) replacing the hand-held `asyncio.Semaphore`; each
document's failure is still isolated inside `DocumentIngest` and folded into
the `IngestionReport` rather than raised, so isolation survives the move to
the engine's own scheduling.

`AWAITS_INVOKE` re-checked in PIR-867 (superseded by PIR-872, below): `specializations/routing/_attempt_tier.py::_AttemptTier`
awaited `CascadeTier.invoke` (the cascade's own bare-callable provider seam,
not a `Tool`) directly. There is no tool knot to substitute — the fix is the
same shape `ToolInvocation` plays for tool calls: a dedicated vending knot,
`_TierInvocation`, whose only body is the call, wired as a real parent;
`_TierAttemptFold` (`error_policy=RECEIVE_ERRORS`) folds its `Ok`/`Err`
outcome into the cascade's state. `_AttemptTier` itself became an
`AgentPipeline` (only the pre-call locked/spend-cap decisions stay
synchronous, since they decide whether to build the call at all).
`AWAITS_INVOKE` then named `_TierInvocation` instead of `_AttemptTier`.
**PIR-872** removed that entry too: a cascade tier *is* a model call, so
`CascadeTier` carries an `LLMProvider` and `_AttemptTier` wires the shared
`LLMChatCall` knot over it; `CascadeTier.invoke` and `_TierInvocation` are
deleted and nothing awaits an invoke inside `process()`.

`GatedAgentResponse` (the `CHECK_ROLE` shadow — a knot joining a value with a
`Gate` so a single-parent gate could feed a multi-input knot) is deleted
(PIR-872): `EvaluatorOptimizerLoop` gates the candidate itself with
`Gate(input=candidate, check=CandidateRejectedCheck(accepted))`, and
`AcceptCheck` is a `Check`. `ConversationMemoryPruner`'s `while True`
(`HAND_ROLLED_WHILE_TRUE_RETRY`) was a pruning loop, not a retry; it now loops
on its real condition.

The bypass ratchet (`tests/specializations/base/test_no_engine_bypass.py`)
is empty for `AWAITS_CHILD_PROCESS`, `RETURNS_INLINE_SOURCE`, `UNRUN_TAPESTRY`,
`DEFINES_INLINE_SOURCE`, `AWAITS_INVOKE`, `LOOP_AWAITS_LLM_OR_TOOL_CALL`,
`USES_ASYNCIO_GATHER` and `HAND_ROLLED_WHILE_TRUE_RETRY`; kept as
`frozenset()` assertions so a regression is loud, not deleted.
`agent/parallel_tool_executor.py::ParallelToolExecutor` is one tool knot per
call under an `Aggregator` with `KnotConfig(retry=, timeout=,
concurrency_group="tools")`, so `GovernedDispatch` owns the inter-attempt
backoff (PIR-872).

**Resolved (PIR-872): `rag/indexing/_raptor_assembler.py`'s clustering loop.**
It stays a deliberate ETL exception (atomic read-check-transform-write cycle
against the vector store: a content-hash dedup short-circuit and a single
final upsert that must see a consistent store), but each level's cluster
summaries now run as a nested run of one `_RaptorSummary` knot per cluster
joined by an `Aggregator`, so every LLM summary call has its own lineage row,
`Result` and admission. What made this a coupling problem before —
`_run_inner` and its hooks lived only on `SubTapestry`, whose `__call__`
requires `process()` to return a sink `Knot` — is gone: core's new
`NestedRunKnot` (§3.2) is that machinery without the sink contract, and
`SubTapestry` is now a `NestedRunKnot` that adds it.
`_RaptorAssembler(Assembler, NestedRunKnot)` keeps returning its `RaptorTree`
value directly.

**Resolved since (PIR-865):** approval denial is a core `Skipped`, not a
`ToolCallRejection` `Err` — see §7's Tool section.

### Authoring, payload types, and docs (WS6a, WS6b)

The builder's `AgentPatternRegistry` (67 canonical pattern names plus the
`rag` alias for `naive_rag`, 68 total — `AgentPatternRegistry.pattern_names()`)
used to be a table disjoint from the `sweet_tea` registry core's YAML loader
reads; every name is now aliased into that same registry at `pirn_agents`
import time (`AgentPatternRegistry.register_with_core_registry`), so a core
YAML document's `callable: react` resolves exactly like `.pattern("react")`
does. `AgentSpec` is now a projection of core's `PipelineSpec`
(`to_pipeline_spec`/`from_pipeline_spec`); `AgentSpecLoader` reads a core
pipeline document directly; the old flat-dict-only dialect is deleted
(PIR-864). `AgentBuilder.build()`'s runtime seed is bound as a named core
`Parameter` instead of a baked constructor kwarg. See
`examples/agents_core_pipeline/` for `tapestry-check` validating an agent
pipeline written entirely in core's YAML vocabulary (WS6a).

**Resolved (PIR-870).** Each of those 66 rows used to restate its class's
full `"module:ClassName"` location by hand — duplicating exactly what
`Registry.fill_registry()` already discovers by scanning `pirn_agents` at
import time, and doubling the cost of a rename or a moved file.
`PatternDescriptor` now carries a bare `class_name` and resolves it through a
`sweet_tea.registry.Registry.entries()` lookup scoped to the `pirn` library
and the auto-fill label, deriving the module from the resolved class's own
`__module__`; only `seed`/`seed_kind` remain hand-declared per pattern name.
`tests/builder/test_pattern_registry_coverage.py` cross-checks the *sweet_tea*
Registry's own view of every `AgentPipeline` subclass against this table
(catching one class — `FailoverLoop`, an internal loop body living outside
`specializations/` — the old pkgutil-based completeness check could not see)
and generates the pattern list from the registry to verify it against a new
"Full Pattern Reference" appendix in `pirn_agents/PATTERNS.md`.

`AgentResponse` is `Payload[GenerationFrame, str]` in place — `data` is the
reply text, `frame` carries `finish_reason`/`usage`/`cost`/`tool_calls`/
`model`/`provider`; the pre-ADR field names stay readable as properties.
`AgentContext` (a flat frozen dataclass with no frame/lineage descriptor) is
replaced by `ConversationPayload = Payload[ConversationFrame, tuple[AgentMessage, ...]]`;
`AgentContext` is deleted (PIR-864).
`docs/domains/agents.md`, `docs/guides/agentic-loops.md`, and every
`pirn_agents` authoring doc (`AGENTIC_USE.md` ×2, `PATTERNS.md`, `TOOLS.md`,
`BUILDER.md`) are rewritten in this vocabulary — core's own nouns first
(`Knot`/`SubTapestry`/`LoopSubTapestry`/`Result`/`Payload`/`Check`/`Gate`/
`Branch`), "tier"/"family"/"spine"/"preset"/"recipe" dropped as primary
vocabulary, every constructor sample verified against the real signature
(WS6b).

*Correctly reused throughout (preserve):* `SubTapestry`/`Source`,
`PirnOpaqueValue` value objects, `DsnScrubber` composition, HITL suspend/resume
(rightly avoids a `Trigger` loop), and raise-site exceptions kept orthogonal
to `ExceptionRecord`.

### House conventions — core-side decisions (PIR-869, PIR-872)

- **Core has no module-level functions (PIR-869, closed by PIR-872).** Every
  former module-level function is a method on its owning class, and no bare
  alias to the old name remains (alpha policy: delete, never deprecate). The
  ambient accessors are `Tapestry.current()`, `Tapestry.current_store()` and
  `Tapestry.current_run_id()` (with `Tapestry.current_emitters()` /
  `Tapestry.current_emitter_error_policy()`); the drivers are the instance
  methods `trigger.run_forever(tapestry, *, on_result, on_error)` and
  `source.run_stream(tapestry, *, on_result, on_error, extra_parameters)`;
  domain discovery is `DomainDiscovery.discover_installed_domains()`; the
  decorator is `@KnotFactory.knot` (also `@KnotFactory.knot(input_schema=...)`).
  The former wrappers are called in class form: `ContentHasher.hash`
  (`core/content_hasher.py`), `CycleDetector.detect`,
  `PipelineLoader.load_yaml`, `TapestryValidator.validate`
  (`check/tapestry_validator.py`), `TracebackRedactor.redact_common_secrets`
  (`managers/traceback_redactor.py`), `WithContinuation.attach`
  (`nodes/with_continuation.py`), `@ConnectionConfigDecorator.apply`,
  `AsyncCallable.is_async_callable`, `KnotSourceRecord.from_knot`,
  `KnotDiff.replay_run` / `KnotDiff.compare_runs`,
  `CeleryDispatcher.register_worker_task`, `MermaidRenderer.for_tapestry` /
  `.for_run`, `TapestryHtmlRenderer.for_tapestry` / `.for_run`,
  `TapestryGraphScanner.scan`, `ExplorerHtmlGenerator.generate`. The core
  entries of `scripts/check_conventions.py`'s module-level-function allowlist
  are gone, and the core conventions baseline is 0 in every category. The
  console scripts point at `TapestryCheckCli.main` and `ExploreCli.main`.
- **Names and constants (PIR-872).** `*Gate` is reserved for `Gate`
  subclasses: the admission interface is `Admission`
  (`engine/admission/admission.py`) with `LimitedAdmission` and
  `UnboundedAdmission`, next to `ChainedAdmission`. Class-level configuration
  is a lowercase `ClassVar`: `InMemoryDataStore.default_max_values`,
  `InMemoryHistory.default_max_runs`, `InvocationIdentity.uncomparable_marker`.
- **Deleted, not deprecated (PIR-872).** The `pirn/emitters/base.py`,
  `pirn/triggers/base.py` and `pirn/streaming/base.py` module shims, the
  `pirn.domains.*` import shim and its `pirn-migrate-imports` codemod
  (`pirn/_migrate/`), and the `Knot._deprecated_since` /
  `_deprecation_notice` construction-warning seam (with its last user,
  `pirn_data`'s `ScdType1Overwrite` — use `MergeUpsert`).
- **`_CloudObjectStore` composes over `ObjectStore`.** `S3DataStore`,
  `GCSDataStore` and `AzureBlobDataStore` no longer open an SDK client per
  call: each lazily builds its connector `ObjectStore` (`S3Store`, `GCSStore`,
  `AzureBlobStore`) through `_build_object_store()` and delegates
  `put`/`get`/`has`/`scrub` to it, so one client serves N operations and
  `DataStore.close()` (a no-op default on the base, awaited by
  `Tapestry.close()` and `async with Tapestry()`) releases it exactly once; a
  closed store reopens lazily. `ObjectStore` gained `exists(key)` (metadata
  presence check; list-based default) and `is_not_found(exc)` (classifies the
  SDK's own missing-object error so the data store can raise `KeyError`).
  Public constructor signatures are unchanged; `S3Store`/`GCSStore` accept
  `session=`, `AzureBlobStore` accepts `credential=`, `AzureBlobConfig` gained
  `account_url`, `S3Config.region` became `str | None` (same default).
  `LocalDiskDataStore` keeps the raw-bytes primitives (its atomic-rename
  write has no connector counterpart).
- **pyright strict is per subpackage, ratcheted.** Each package's
  `[tool.pyright].strict` lists the subpackages that pass strict with 0
  errors (core: `check`, `emitters`, `exceptions`,
  `managers`, `recording`, `security`, `streaming`, `viz`, `yaml_loader` and
  the root modules; `backends`, `core`, `connectors`, `engine`, `nodes`,
  `triggers` are the burn-down). New subpackages start strict, a subpackage
  joins at 0, none regresses — `scripts/check_pyright_strict_list.py` enforces
  it in CI and `docs/architecture/ci-pipelines.md` holds the table. The only
  strict rule the house style contradicts, `reportUnnecessaryIsInstance`, is
  suppressed per file with a reason; the runtime guard is never deleted.

**PIR-868 (WS6b follow-on).** The 11 specialization-pattern `*Result` value
objects (`EvaluatorOptimizerResult`, `LatsResult`, `OrchestratorWorkersResult`,
`WorkerTaskResult`, `PlanReActResult`, `PromptChainResult`, `SimulationResult`,
`ReflexionResult`, `ReWooResult`, `FallbackResult`, `SelfAskResult`) are now
`Payload[<Frame>, D]` too, with `AgentResult` reduced to a thin generic
`Payload` base; pre-ADR field names stay readable as properties.
`document_processing/_document_loader.py`'s ingestor (reading files/HTTP
inside `process()`) is deleted per the assembler/disassembler pattern and
replaced by `DocumentSource` (a `Source` knot modeled on
`ObjectStoreReadSource`, bytes out) feeding `DocumentAssembler` (an
`Assembler`, bytes in, no I/O); `DocumentIngestionPipeline`'s public
constructor is unchanged.

### Agents vocabulary and house conventions (PIR-872)

- **No agents module-level functions remain.** The 19 agents entries of
  `_MODULE_LEVEL_FUNCTION_ALLOWLIST` are gone: each former wrapper is its
  owning class's static method, with no alias (`OptionalImport.require`,
  `ApprovalHook.authorize`, `ConnectorLifespan.manage`, `AsTool.wrap`,
  `ToolDecorator.decorate`, `ReciprocalRankFusion.fuse`, `DecayFunction.score`,
  `ToolTestHarness.assert_tool_schema`/`assert_tool_schema_shape`/`run_tool`/
  `collect_tool_stream`, `Bundles.*_toolset`). The agents conventions baseline is
  0 in every category: `EvalGate` (not a `Gate`) is `EvalRegressionCheck`; every
  `process()` catch-all is `**_`; the six unmarked closures are static methods.
- **Knot Rules 1 and 4 hold without exceptions.** `MapAgent` wires every setting
  as a declared input and validates in `process()`; a delegated specialist
  reaches `SpecialistInvocation`/`ReviewerInvocation` as a `SpecialistHandle`
  (a non-`Knot` `PirnOpaqueValue`, so an ordinary input rather than a parent);
  the SQL write policy is a `ClassVar` on distinct classes (`SQLAgent` read-only,
  `ReadWriteSQLAgent` writes) instead of instance state, so no upstream knot can
  flip it. `docs/contributing/knot-design-rules.md` Rule 4 now describes that
  shape instead of a constructor-state exception.
- **An outcome is `Ok|Err|Skipped`.** `BatchItemStatus`, `ToolStatus` and
  `FailoverOutcome` are deleted: `BatchItemResult.outcome`, `ToolResult.outcome`
  and `FailoverAttempt.result` are the `Result`; a timeout is an `Err` whose error
  type is `KnotTimeoutError`; a resumed item or open circuit is a `Skipped` with a
  reason. `ToolResult.status` survives only as a model-facing string derived from
  the `Result`. `RetryClassification` was never an outcome — it is
  `RetrySafetyClassifier.is_safe() -> bool`.
- **Stores and structural types are named inventories.** `ResultCache` no longer
  re-exposes `get`/`put`/`has` over its `DataStore` (raw access is `cache.store`)
  and `VectorMemoIndex` is deleted. The keyed stores that remain are listed with a
  reason in `tests/test_store_inventory_ratchet.py` (the `MemoryStore` similarity
  seam, its vector-database and S3 adapters, and `KeyedLineageStore` onto core's
  lineage plane); the content blocks, `AgentMessage` and `FinishReason` are listed
  in `tests/types/test_types_are_payload_or_frame.py`. `BatchProgress` is a pure
  per-fire summary; `RunState` is a `RunHistory` read model, not a checkpoint.

---

## 7. The core / agents boundary

**Principle.** The agents layer adds LLM-interaction concepts core deliberately lacks — tools, tool-calling, agent patterns, prompt composition — but **composes them from core primitives** rather than re-implementing execution, outcomes, schema, or persistence.

**What belongs where:**
- **Core** — the dataflow engine: `Knot`, `Result` (`Ok\|Err\|Skipped`), `Payload`, `Tapestry`, transports, triggers, nodes, dispatchers, connectors + capabilities, backend stores, and emitters. Provider-neutral; no LLM-orchestration semantics — core does not even own the model-wire provider contracts.
- **Agents (and sibling domains)** — the LLM-interaction layer: the `LLMProvider`/`EmbeddingProvider` model-wire contracts (each consuming domain owns its own copy — `pirn_agents.llm_provider`/`pirn_agents.embedding_provider`, `pirn_health.llm_provider`, `pirn_ml.embedding_provider`), `Tool`/`ToolCall`/`ToolResult`, the frame nouns that pair with core's `Payload` (`GenerationFrame`, `ConversationFrame` — WS6b), agent patterns (RAG/ReAct/plan-execute/…), prompt composition, the tool-calling loop, agent-as-tool.

**Canonical case — the Tool. RESOLVED (ADR WS1, 2026-09-13).** A `Tool` is correctly agents-layer (core has no notion of a name + NL description + JSON schema *for a model*), and it is now **composed from** core:
- `Tool(Knot)` — a tool is a `Knot` *class*; `process()` is its execution and its declared inputs are the call's arguments. `Tool.declaration()` (name, description, `input_json_schema()`) is the only agents-layer addition. One call = one tool knot the engine runs (`ToolFactory.for_call(call)`), so each call has its own `Result`, lineage row, timeout/retry (`KnotConfig`) and concurrency group (`"tools"`).
- `ToolFactory(KnotFactory, PirnOpaqueValue)` is the *capability* value a toolset holds: a tool class plus bound collaborators (`Tool.bind(store=…)`), defaults and a name. `@ToolDecorator.decorate` is `@KnotFactory.knot` plus a declaration; `McpTool` is `KnotFactory.from_schema` over the remote schema; an agent-as-tool is `AgentTool` over an `AgentToolCall(SubTapestry)` whose cycle/depth guard is core's `RunNesting` (no agents nesting state; the shared budget meter and pooled provider ride `AgentToolPolicy`, PIR-872).
- Outcomes are `Ok\|Err\|Skipped`; `ToolResult` is the model-facing view whose `outcome` *is* the call's `Result` (PIR-872 deleted the parallel `ToolStatus` enum; `status` is a string derived from the variant and error type), and PIR-865 gave it its gated/approval rendering (`ToolResult.from_result(call_id, result, lineage)`; the denial's reason arrives on the `Skipped` itself since PIR-872), so the codec builds this view and reads `Result` through it rather than around it. A call refused for validation or an unknown tool is a `ToolCallRejection` knot recording its `Err`, never a raise outside the engine; a call refused for **approval** is a `Skipped`, not a `ToolCallRejection` — see the approval bullet below.
- **Deleted (PIR-864):** `Tool.invoke`, `ToolFactory.invoke`/`as_tool_result`/`from_legacy`, `BaseTool`, `ToolSchemaCompiler`, `ArgumentValidator`, `AgentSchemaDeriver`, `AgentInvoker`, `ToolInvocationHook`, `ParallelToolExecutor(hook=, retries=, retry_policy=, rng=, sleep=)`'s legacy constructor kwargs, `_FanoutRunner`, and `AsyncFanoutEngine` (machinery removed once `MapAgent` moved onto `Map`/`Aggregator` in WS4b) — every production and test caller now goes through the composed shapes above. See `CHANGELOG.md`'s "Removed" section for the full name → replacement table.
- Observability (WS4a wired in): a tool call is one `"tool"` `StatusEvent` through `AgentCallRecorder` — emitted by `ToolInvocation` for its call (outer run, its own id; it claims the report from the tool knot), by a tool knot wired directly (a fan-out) for itself, by `ToolCallRejection` for a refused call and by `AgentToolCall` for an agent-as-tool call. LLM-calling knots in the tools lane (`RagTool`, `Planner`, `ToolSelector`, `ReActStepExecutor`) report `"llm"` events through `RecordedLlmCall`. A denied approval reports no `"tool"` event for the tool's own identity at all — `process()`, and the `Tool.__call__` recorder inside it, never run; a *container* (`ToolInvocation`) that reports its own view regardless of outcome still fires, unchanged, attributed to its own knot id.
- **Approval — RESOLVED (PIR-865, lineage PIR-872).** `pirn_agents.agent.tool_approval_check.ToolApprovalCheck` (a core `Check`; named `ToolApprovalCheck` rather than `ApprovalCheck` because `specializations/human_in_the_loop/approval_check.py::ApprovalCheck` already holds that name for an unrelated seam) evaluates the same policy `ApprovalHook.authorize` always implemented. `ToolFactory.for_call` wires it behind a core `Gate` — the gate's `input` is a `Parameter` carrying the call's resolved arguments, and the gate itself is passed as an extra, undeclared `Knot`-valued kwarg (an *implicit parent*, `Knot._validate_kwargs_against_signature`'s existing seam for exactly this) to the constructed tool knot — whenever `ToolPermissions.approval_required` is set; an unrestricted capability is never gated. A denial closes the gate, so the engine's default `SKIP_IF_PARENT_FAILED` policy skips the tool knot without ever calling `process()`. The skip names itself: `ToolApprovalCheck.skip_reason = "approval_denied"` is core's `Check.skip_reason` seam — the closed gate records that reason on its own lineage row and returns `Skipped(reason="approval_denied", propagates=True)`, and the engine gives every knot skipped only by propagating skips of one shared reason that same reason (`Skipped.propagates`, recorded as `extra["skip_propagates"]` so replay propagates it too). The tool knot's own row and its `Skipped` therefore say `"approval_denied"`, and `ToolResult.from_result` renders it as `"call skipped: approval denied"` with no out-of-band `gated=` flag. `ToolResult` keeps a `Skipped` outcome as `Skipped` (status `"skipped"`), instead of the old behaviour of fabricating an `Err`/`ERROR` view for every `Skipped`. All six call sites that construct a tool knot for a call (`ToolFactory.for_call`/`run_call`, `ToolInvocation`, `ParallelToolExecutor`, `ParallelToolCaller`, `ToolChain`, `ReActStepExecutor`) gained an `approval_hook` input threaded to `for_call`. `ToolFactory.run_call` also stopped being a bare `await knot({})` for a gated call specifically: that pattern never resolves a genuine `Knot` parent (only `Aggregator`/engine dispatch does), which would have silently run the tool regardless of the gate's decision — a gated call now runs through a real `Tapestry.run(terminals=knot)` pass instead, reusing `ToolCallCodec.outcomes_of` to read the outcome back out; an ungated call keeps the original fast bare-call path unchanged. `ToolCallRejection` is unchanged and keeps its narrower job (unregistered tool, refused arguments) — that is a rejection, not an approval decision.
- Core seams this needed (all in `SubTapestry`): `_make_inner_tapestry()` (a container chooses its inner `Tapestry(...)` — traceback filter, `max_nesting_depth`, `ConcurrencyLimits`), `_inner_failures_reach_sink` (a container whose sink *consumes* inner `Err`s does not raise `SubTapestryError`), a `Skipped` sink passes through as `Skipped`, and `_nesting_key` is qualified by the knot id (two instances of one agent class may nest; the same instance may not). `SubTapestryError`'s message now names the inner failures.

**Second case — the response/conversation shape. RESOLVED (ADR WS6b, 2026-09-13).**
`AgentResponse` and the conversation window were flat frozen dataclasses with
no frame/metadata lineage descriptor — agents (and `pirn_data`) were the only
domains with no `Payload` type. They are now core's own `Payload[Frame, Data]`:
`AgentResponse = Payload[GenerationFrame, str]`, `ConversationPayload =
Payload[ConversationFrame, tuple[AgentMessage, ...]]`. `GenerationFrame` and
`ConversationFrame` are the legitimate agents-layer nouns (LLM-turn and
conversation-window metadata core has no name for); `Payload` itself,
`derive()`, and `_pirn_audit_dict()`-based content addressing are core's,
unchanged. `AgentContext` (the pre-ADR name) is deleted (PIR-864).

**Rule of thumb.** A new agents abstraction is legitimate when it *names an LLM-interaction concept core lacks*. It is a smell when it *re-implements execution, outcomes, schema, persistence, or concurrency* core already provides — model those the way core does (a `NotImplementedError` base whose execution is a `Knot`). Ratifying this boundary is WS0's core deliverable.

**Core seam gap found by ADR WS3 part 1, closed in part 2.** Neither `DataStore` nor `RunHistory` used to mix in `PirnOpaqueValue` (§1.3), so no `Knot.process()` could declare either as a typed parameter — `Knot._build_adapters` calls `TypeAdapter(ann)` unconditionally for every declared, non-`Knot` parameter, which raises `PydanticSchemaGenerationError` for a type with no pydantic-core schema. `pirn_agents.memory.memory_lineage_recall.MemoryLineageRecall` (part 1) is still typed `Any` with manual `isinstance` checks — a working, if less strongly typed, pattern — but part 2's `pirn_agents.sessions.run_resumer.RunResumer` and `.approval_resumer.ApprovalResumer` declare `RunHistory`/`DataStore` directly now that both classes mix in `PirnOpaqueValue`. Gated across all seven packages when made (a core interface every backend subclasses).

---

*Generated from a full read of `packages/pirn-core/pirn`. Keep this in sync when core's base classes change.*
