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
| `content_hash(value, *, strict=False)` | function | — | `core/hashing.py`, backed by `_ContentHasher` — the one content-addressing seam (`sha256:`-prefixed). Default is best-effort: an opaque leaf degrades to a `sha256:unhashable:<type>` sentinel. `strict=True` raises `UnhashableValueError` (`PirnError, TypeError`) naming the innermost offending type instead — for a caller (a cache key, a dedup key) where the sentinel's silent collision risk is unacceptable, not just an inconvenience. (ADR agents-speaks-core WS2 part 2) |

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
| `ExecutionPlane` (`core/execution_plane.py`) | value-object | the scheduling half of a run — `dispatcher`, `gate` + `limits`, `admission_observers`, `replay`, `identity_resolver` — published by `Tapestry.run` for the run's duration (`ExecutionPlane.current()`) and **inherited by every inner run** for whatever the inner tapestry did not name: the gate by identity, so `ConcurrencyLimits` are one budget across the run tree. Container knots (`Knot._holds_admission_slot = False`: `SubTapestry`, loop iterations) take no slot and may not carry a `concurrency_group`. Per-container overrides: `SubTapestry._run_inner(dispatcher=, concurrency=, admission_observers=)` or the `_inner_dispatcher` / `_inner_concurrency` / `_inner_admission_observers` hooks (ADR WS0b) |

**Idiom:** choose parallelism by swapping a `Dispatcher`, not by changing knots. Agent batch/fleet execution should compose or subclass a dispatcher, not re-implement a bounded-concurrency loop. An inner run inherits the outer dispatcher and admission gate; a container that needs its own overrides them through `_run_inner` / the `_inner_*` hooks — **never by assigning an inner tapestry's private fields** (ratcheted in agents' `tests/core_seams/test_execution_plane_reach_through.py`).

**Idiom (resilience):** a per-call timeout or retry is `KnotConfig(timeout=..., retry=KnotRetryPolicy(...))` on the knot, honoured by the engine. A knot that wraps its own body in `wait_for` or a `while True` retry re-implements the engine and loses the attempt count from lineage.

### 3.6 Emitters + Managers — `emitters/`, `managers/`
| Type | Kind | Contract |
|---|---|---|
| `Emitter` (`emitters/emitter.py`) | interface-base | receives status/lineage events; `log`/`otel`/`kafka`/`valkey`/`webhook` impls; `emitter_error_policy` governs failures. **`on_knot_result(knot_id, result, lineage)`** (ADR WS0b) is the live per-knot stream: awaited by the engine the moment a knot settles, with the full `Ok`/`Err`/`Skipped` (the `Err`'s rebound `ExceptionRecord` included) and its lineage row, before the knot's children start — the hook a fan-out consumer streams per-item outcomes from before the join completes. No-op default; same error policy as `on_lineage` |
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
- **Is it event-driven?** → implement `Trigger` and use `run_forever`, don't hand-roll a consume loop.
- **Is it parallel execution?** → compose a `Dispatcher`, don't re-implement concurrency.
- **Does something succeed/fail/skip?** → `Ok \| Err \| Skipped`, not a new enum.
- **Is it pure logic with no state?** → a plain class with methods; a module-level function only for a genuine decorator or a true "only-way" adapter.

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
find "what changed" without reconstructing which PR did it. Deprecated names
are one-cycle shims (`DeprecationWarning` on construction), not deletions,
unless marked otherwise.

### Retry, timeout, and nesting (core seams, WS0)

Core now owns per-knot timeout and retry (`KnotConfig.timeout` →
`Err(KnotTimeoutError)`, `KnotConfig.retry: KnotRetryPolicy` run by
`GovernedDispatch`, attempts recorded in lineage) and the nested-run depth and
cycle guard (`RunNesting` on every run, `Tapestry(max_nesting_depth=)`,
inherited and only tightened by inner tapestries). Agents' `llm/retry_policy.py::RetryPolicy`,
`exceptions/tool_timeout_error.py::ToolTimeoutError`, `AgentNestingConfig`,
`AgentToolContext`, `AgentInvoker`, and the `AgentRecursionError` family are
listed as shadows in `tests/core_seams/test_core_seam_shadows.py` pending
migration (`AgentToolContext` already composes core's `RunNesting` frame —
see its module docstring — but is not yet collapsed onto it entirely).

### Tool — RESOLVED (WS1)

A `Tool` is correctly agents-layer (core has no notion of a name + NL
description + JSON schema *for a model*); it is now **composed from** core
rather than parallel to it. See §7 for the full case — it is the canonical
example of the boundary this ADR draws.

### Outcomes, errors, and hashing (WS2)

`Ok|Err|Skipped` is now the outcome vocabulary agents targets: `BatchItemResult`
gained `to_result()`/`from_result()` bridges; `pirn_agents.resilience.FailoverAttempt`
→ `Result` per candidate, replacing the `FailoverOutcome` enum; `ModelCascadeRouter`/
`FallbackChain`/`FailoverChain`'s fold-accumulator chains now run as a
`LoopSubTapestry` (`_CascadeLoop`/`_FallbackLoop`/`_FailoverLoop`) that stops
scheduling once the chain locks, rather than a static unrolled chain that
still built a knot per candidate past the lock point. 8 of the 18 agents
exception roots the ADR found now also subclass `pirn.exceptions.pirn_error.PirnError`
(`ToolInvocationError`, `AgentRecursionError`, `SandboxDisabledError`,
`UnsupportedModalityError`, `MissingCassetteEntryError`, `InjectionDetectedError`,
`McpTrustError`, `UntrustedDirectiveError`); the other 10 are frozen in
`tests/test_core_vocabulary_ratchet.py`. `content_hash` (§4.4) is the one
hashing path for new code; `CanonicalJson`/`ContentAddress` are one-cycle
deprecated wrappers around it.

**Still open:** `BatchItemStatus` is not deleted (`MapAgent` scheduling still
owns it); `CanonicalJson.digest`/`encode` still compute their own bare-hex
form at 3 of 7 call sites (`resilience/idempotency_key_assigner.py`,
`builder/agent_knot_id_factory.py`, `sessions/run_checkpoint.py`) that persist
or transmit the digest as a durable/dedup key with no migration path yet;
`caching/content_address.py` is not migrated either, because `content_hash`'s
best-effort opaque-value fallback would reopen the PIR-785 cache-collision bug
`ContentAddress` exists to prevent.

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
diverges. `CassetteRecorder` is now a thin adapter over `Tapestry.run()`/
`Tapestry.run(replay=...)`; `TrajectoryEmitter` captures every knot's lineage
into a `RunTrace` via `on_lineage`, no manual `.record()` calls. `DataStore`
and `RunHistory` both now mix in `PirnOpaqueValue` (§1.3), closing the gap
that kept `Knot.process()` from declaring either as a typed parameter — WS3's
own `RunResumer`/`ApprovalResumer` are the first to declare them directly.

Deprecated: `RunCheckpoint`/`RunCheckpointer`/`SessionStore`/
`InMemorySessionStore`/`PersistedSessionStore`/`ThreadRepository`/
`MemoryStoreKeyIndex`, `Cassette*`/`TrajectoryRecorder`/`TraceDiffer`.

### Observability (WS4a)

The second event bus is collapsed: `StatusEvent` gained a typed
`extra: dict[str, Any]` field (core touch); `EmitterFanout.emit_status` (core
touch) fans an ad hoc `StatusEvent` out to a run's emitters from inside an
async `process()`; `OpenTelemetryEmitter`/`LogEmitter` (core touch) render a
non-empty `extra` as span attributes / a log field. `AgentCallRecorder` is now
the one call every LLM/tool/retrieval call site uses. Deprecated:
`Tracer`/`Span`/`SpanKind`/`SpanStatus`/`OpenSpanEntry`/`ObservabilitySink`/
`OtelSink`/`LoggingSink`/`SpanEmittingToolInvocationHook` — all still forward
into `AgentCallRecorder`.

**Partially wired:** `SecretRedactor.default_traceback_filter()` returns a
`Callable[[str], str]` in the exact shape `Tapestry`/`ExceptionManager.traceback_filter`
expects, and `SecretRedactingLogFilter.install()` attaches (idempotently,
opt-in) to the package logger — but actually passing
`traceback_filter=SecretRedactor.default_traceback_filter()` into the
`Tapestry(...)` agents constructs (the pattern registry, the builder,
`AgentPipeline`'s outer run) is not done; `builder/**` and `specializations/**`
are untouched by this wiring.

### Scheduling and concurrency (WS4b, "one scheduler")

`MapAgent` is a `SubTapestry` whose inner graph is one `_MapItem` knot per
input item joined by a core `Aggregator` under `ErrorPolicy.RECEIVE_ERRORS`;
concurrency is `KnotConfig(concurrency_group=)` + `ConcurrencyLimits`; per-item
timeout/retry is `KnotConfig.timeout`/`KnotConfig.retry`, run by
`GovernedDispatch`. Resume-after-crash is a `RunHistory.query_lineage_by_knot_id`
lookup on the item's knot id (`item:<batch_id>:<key>`), not an F14 checkpoint
store. `AdaptiveConcurrencyController` is now an `AdmissionObserver` (additive
increase on `on_release`, multiplicative decrease on a new `on_throttle()`
called directly by `_MapItem`). `TriggeredBatch`/`IntervalTrigger`/`EventTrigger`
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

Deprecated: `BatchCheckpointer`/`BatchScheduler`, `AsyncFanoutEngine`/
`_FanoutRunner` (machinery removed once `MapAgent` moved onto `Map`/`Aggregator`).

**Still open:** `Bulkhead`/`BulkheadConfig` and `BackpressureSemaphore`/
`ConcurrencyConfig` still hold their own `asyncio.Semaphore`-shaped pools,
called directly by `agent/parallel_tool_executor.py`, `evaluation/run_eval.py`,
and three `specializations/` pipelines — `document_processing/ingestion_pipeline.py`,
`multi_agent/orchestrator_workers.py`, `rewoo/rewoo_pipeline.py`. Migrating
their *enforcement* to `LimitedAdmissionGate` needs those call sites moved
onto a knot-scoped concurrency group first, or there are two enforcement
paths rather than one. `caching/prompt_cache.py::PromptCache` also stays
outside this migration: its `get`/`set`/`__len__` are deliberately
synchronous, and `DataStore` is async-only, so routing values through it would
force a breaking signature change this ADR did not authorize unilaterally.

### Control-flow vocabulary (WS5a, WS5b)

`Check(Knot)` names the boolean-verdict role and `Gate(check=)` consumes it
directly. `LoopSubTapestry.astep`/`afold` give an awaitable loop step.
`ResolvedValueKnot`/`MessagesPassthrough`'s constant-seed use →
`core/parameter.py`'s `Parameter` (16 call sites across 12 files).
`ConsensusAggregator` → `ConsensusPipeline`. All 12 inventoried imperative
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
`_ChunkTranslator` (`specializations/document_processing/`) and
`FactClaimVerifier` (`specializations/guardrails/`) translate/verify
independent items — chunk N's translation and claim N's search never depend
on item N-1's outcome — so each now fans out one per-item knot
(`_ChunkTranslation` / `_ClaimVerification`) into an `Aggregator`, in the
`ParallelToolCaller` style, instead of awaiting `llm.chat`/`store.search` in a
hand-rolled `for` loop. `PlanExecutor` (`specializations/plan_and_execute/`)
is different: step N's prompt genuinely includes every prior step's result,
so it wires a `LoopSubTapestry` (`_PlanStepLoop`) instead — the state
threaded across iterations is the running tuple of step results.

Three more `USES_ASYNCIO_GATHER` sites fixed in PIR-867: `HybridRetriever`
(`retrieval/`) now wires its dense and lexical arms as two knots
(`_DenseIds`/`_LexicalIds`, the BM25 side still offloading to a worker thread
internally via `asyncio.to_thread`) into an `Aggregator`, so it is a
`SubTapestry` now rather than a plain `Knot` — `HybridRetrieverBase` stays a
plain `Retriever`/`Knot` base since `HybridGraphRetriever` still needs that
shape, so `HybridRetriever` picks up `SubTapestry` itself
(`class HybridRetriever(SubTapestry, HybridRetrieverBase)`).
`_ChunkEmbedderStore` (`specializations/document_processing/`) wires one
`_ChunkStoreWrite` per chunk into an `Aggregator` (the batched embedding call
itself stays a single call — batching is the reason the embedder gets every
chunk at once). `_IngestionRunner` (`specializations/document_processing/`)
wires one `_DocumentIngest` per source document into an `Aggregator`, with a
`ConcurrencyLimits` group cap set via the `_inner_concurrency()` hook
(`MapAgent`'s own lever) replacing the hand-held `asyncio.Semaphore`; each
document's failure is still isolated inside `_DocumentIngest` and folded into
the `IngestionReport` rather than raised, so isolation survives the move to
the engine's own scheduling.

`AWAITS_INVOKE` re-checked in PIR-867: `specializations/routing/_attempt_tier.py::_AttemptTier`
awaited `CascadeTier.invoke` (the cascade's own bare-callable provider seam,
not a `Tool`) directly. There is no tool knot to substitute — the fix is the
same shape `ToolInvocation` plays for tool calls: a dedicated vending knot,
`_TierInvocation`, whose only body is the call, wired as a real parent;
`_TierAttemptFold` (`error_policy=RECEIVE_ERRORS`) folds its `Ok`/`Err`
outcome into the cascade's state. `_AttemptTier` itself became an
`AgentPipeline` (only the pre-call locked/spend-cap decisions stay
synchronous, since they decide whether to build the call at all).
`AWAITS_INVOKE` now names `_TierInvocation` instead of `_AttemptTier` — a
sanctioned entry, not a fixed one, since the underlying call has to happen
somewhere.

The bypass ratchet (`tests/specializations/base/test_no_engine_bypass.py`)
is empty for `AWAITS_CHILD_PROCESS`, `RETURNS_INLINE_SOURCE`, `UNRUN_TAPESTRY`,
`DEFINES_INLINE_SOURCE`, `LOOP_AWAITS_LLM_OR_TOOL_CALL`, and
`USES_ASYNCIO_GATHER`; kept as `frozenset()` assertions so a regression is
loud, not deleted.

**Still open** (frozen in the same ratchet, not this ADR's blast radius to
fix unilaterally):
- `rag/indexing/_raptor_assembler.py`'s clustering loop — a deliberate ETL
  exception (atomic read-check-transform-write cycle against the vector
  store; a content-hash dedup short-circuit and a final upsert that must see
  a consistent store). PIR-867 re-evaluated giving each level's per-cluster
  summarization its own lineage row via `SubTapestry._run_inner` called
  *inside* the atomic method (keeping the dedup short-circuit and the single
  final upsert): `_run_inner` depends on hooks and constructor state that
  only exist on `SubTapestry`, whose `__call__` in turn hard-requires
  `process()` to return a `Knot` — the opposite of what this atomic
  assembler needs (return the built `RaptorTree` value once). Getting the
  method without the contract means multiply inheriting `SubTapestry`
  alongside `Assembler` and overriding `__call__` back to `Knot.__call__`,
  a fragile coupling for one knot's observability. Still deferred: a core
  primitive for "run a nested tapestry from a plain `Knot`" would resolve
  it; absent that, whether per-summary observability is worth the coupling
  is a product call, not made here.
- `agent/parallel_tool_executor.py::ParallelToolExecutor`'s own
  `asyncio.gather` is a deliberate deferral — its per-call retry/timeout
  richness needs real inter-attempt backoff sleep, not expressible as a
  static `Aggregator` fan-out.
- **Approval denial** stays a `ToolCallRejection` `Err` this cycle
  (behaviour-preserving); the next-cycle shape is `ApprovalCheck(Check)` →
  `Gate(check=)` so a denied call is `Skipped` instead.

### Authoring, payload types, and docs (WS6a, WS6b)

The builder's `AgentPatternRegistry` (66 canonical pattern names plus the
`rag` alias for `naive_rag`, 67 total — `AgentPatternRegistry.pattern_names()`)
used to be a table disjoint from the `sweet_tea` registry core's YAML loader
reads; every name is now aliased into that same registry at `pirn_agents`
import time (`AgentPatternRegistry.register_with_core_registry`), so a core
YAML document's `callable: react` resolves exactly like `.pattern("react")`
does. `AgentSpec` is now a projection of core's `PipelineSpec`
(`to_pipeline_spec`/`from_pipeline_spec`); `AgentSpecLoader` accepts a core
pipeline document directly, deprecating the old flat-dict-only dialect one
cycle. `AgentBuilder.build()`'s runtime seed is bound as a named core
`Parameter` instead of a baked constructor kwarg. See
`examples/agents_core_pipeline/` for `tapestry-check` validating an agent
pipeline written entirely in core's YAML vocabulary (WS6a).

`AgentResponse` is `Payload[GenerationFrame, str]` in place — `data` is the
reply text, `frame` carries `finish_reason`/`usage`/`cost`/`tool_calls`/
`model`/`provider`; the pre-ADR field names stay readable as properties.
`AgentContext` (a flat frozen dataclass with no frame/lineage descriptor) is
replaced by `ConversationPayload = Payload[ConversationFrame, tuple[AgentMessage, ...]]`,
with `AgentContext` kept importable for one cycle as a deprecated subclass.
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

---

## 7. The core / agents boundary

**Principle.** The agents layer adds LLM-interaction concepts core deliberately lacks — tools, tool-calling, agent patterns, prompt composition — but **composes them from core primitives** rather than re-implementing execution, outcomes, schema, or persistence.

**What belongs where:**
- **Core** — the dataflow engine: `Knot`, `Result` (`Ok\|Err\|Skipped`), `Payload`, `Tapestry`, transports, triggers, nodes, dispatchers, connectors + capabilities, backend stores, and emitters. Provider-neutral; no LLM-orchestration semantics — core does not even own the model-wire provider contracts.
- **Agents (and sibling domains)** — the LLM-interaction layer: the `LLMProvider`/`EmbeddingProvider` model-wire contracts (each consuming domain owns its own copy — `pirn_agents.llm_provider`/`pirn_agents.embedding_provider`, `pirn_health.llm_provider`, `pirn_ml.embedding_provider`), `Tool`/`ToolCall`/`ToolResult`, the frame nouns that pair with core's `Payload` (`GenerationFrame`, `ConversationFrame` — WS6b), agent patterns (RAG/ReAct/plan-execute/…), prompt composition, the tool-calling loop, agent-as-tool.

**Canonical case — the Tool. RESOLVED (ADR WS1, 2026-09-13).** A `Tool` is correctly agents-layer (core has no notion of a name + NL description + JSON schema *for a model*), and it is now **composed from** core:
- `Tool(Knot)` — a tool is a `Knot` *class*; `process()` is its execution and its declared inputs are the call's arguments. `Tool.declaration()` (name, description, `input_json_schema()`) is the only agents-layer addition. One call = one tool knot the engine runs (`ToolFactory.for_call(call)`), so each call has its own `Result`, lineage row, timeout/retry (`KnotConfig`) and concurrency group (`"tools"`).
- `ToolFactory(KnotFactory, PirnOpaqueValue)` is the *capability* value a toolset holds: a tool class plus bound collaborators (`Tool.bind(store=…)`), defaults and a name. `@tool` is `@knot` plus a declaration; `McpTool` is `KnotFactory.from_schema` over the remote schema; an agent-as-tool is `AgentTool` over an `AgentToolCall(SubTapestry)` whose cycle/depth guard is core's `RunNesting`.
- Outcomes are `Ok\|Err\|Skipped`; `ToolResult`/`ToolStatus` survive one cycle as a deprecated *view* built by `ToolResult.from_result(call_id, result, lineage)` and the codec reads `Result` directly. A refused call (approval, validation, unknown tool) is a `ToolCallRejection` knot recording its `Err`, never a raise outside the engine.
- Deprecated for one cycle (thin shims that warn): `Tool.invoke`, `ToolFactory.invoke`, `BaseTool`, `ToolSchemaCompiler`, `ArgumentValidator`, `AgentSchemaDeriver`, `AgentInvoker`, `ToolInvocationHook` and `ParallelToolExecutor(hook=, retries=, retry_policy=, rng=, sleep=)`, `_FanoutRunner` and `AsyncFanoutEngine` (machinery removed once `MapAgent` moved onto `Map`/`Aggregator` in WS4b; the names warn on construction).
- Observability (WS4a wired in): a tool call is one `"tool"` `StatusEvent` through `AgentCallRecorder` — emitted by `ToolInvocation` for its call (outer run, its own id; it claims the report from the tool knot), by a tool knot wired directly (a fan-out) for itself, by `ToolCallRejection` for a refused call and by `AgentToolCall` for an agent-as-tool call. LLM-calling knots in the tools lane (`RagTool`, `Planner`, `ToolSelector`, `ReActStepExecutor`) report `"llm"` events through `RecordedLlmCall`.
- Approval denial stays a `ToolCallRejection` `Err` this cycle (behaviour-preserving); the next-cycle shape is `ApprovalCheck(Check)` → `Gate(check=)` so a denied call is `Skipped`.
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
unchanged. `AgentContext` (the pre-ADR name) is a one-cycle deprecated
subclass.

**Rule of thumb.** A new agents abstraction is legitimate when it *names an LLM-interaction concept core lacks*. It is a smell when it *re-implements execution, outcomes, schema, persistence, or concurrency* core already provides — model those the way core does (a `NotImplementedError` base whose execution is a `Knot`). Ratifying this boundary is WS0's core deliverable.

**Core seam gap found by ADR WS3 part 1, closed in part 2.** Neither `DataStore` nor `RunHistory` used to mix in `PirnOpaqueValue` (§1.3), so no `Knot.process()` could declare either as a typed parameter — `Knot._build_adapters` calls `TypeAdapter(ann)` unconditionally for every declared, non-`Knot` parameter, which raises `PydanticSchemaGenerationError` for a type with no pydantic-core schema. `pirn_agents.memory.memory_lineage_recall.MemoryLineageRecall` (part 1) is still typed `Any` with manual `isinstance` checks — a working, if less strongly typed, pattern — but part 2's `pirn_agents.sessions.run_resumer.RunResumer` and `.approval_resumer.ApprovalResumer` declare `RunHistory`/`DataStore` directly now that both classes mix in `PirnOpaqueValue`. Gated across all seven packages when made (a core interface every backend subclasses).

---

*Generated from a full read of `packages/pirn-core/pirn`. Keep this in sync when core's base classes change.*
