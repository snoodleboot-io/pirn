# Changelog

All notable changes to pirn are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

#### `KnotRetryPolicy.run` — the core retry schedule below the knot boundary (PIR-872)

`pirn.core.knot_retry_policy.KnotRetryPolicy.run(attempt, *, call_id=, retry_on=, retry_after_hint=, sleep=, rng=)` awaits a zero-argument attempt under the same `should_retry` / `delay_before_retry` decision `GovernedDispatch` applies to a knot (over an `ExceptionRecord` built from the live exception), for calls that are not knot dispatches — an HTTP POST, an embedding batch, a session reconnect. `retry_on` / `retry_after_hint` narrow the policy with live-exception checks (an `isinstance`, a `Retry-After` attribute); a cancellation is never retried.

#### Inner runs inherit the execution plane (ADR agents-speaks-core, WS0b)

- `pirn/core/execution_plane.py` — `ExecutionPlane`: the dispatcher, admission gate + `ConcurrencyLimits`, admission observers, replay posture and identity resolver a run executes under. `Tapestry.run` publishes it for the run's duration (`ExecutionPlane.current()`) and every `SubTapestry` inner run / `LoopSubTapestry` iteration inherits whatever its own tapestry did not name. The gate is inherited **by identity**, so `max_in_flight` and group caps are one budget across the run tree (PIR-841 slice 3).
- Container knots are slot-free: `Knot._holds_admission_slot` (`False` on `SubTapestry` and loop iterations), `AdmissionTicket.held`; the `ReadyQueue` admits them without the gate, so a container can never deadlock on a slot its own leaves need. A `SubTapestry` with a `concurrency_group` now raises `ValueError` at construction.
- `LimitedAdmissionGate` is thread-safe (lock-guarded counters, waiters woken on their own loop) for inner runs under `ThreadDispatcher`, and tracks tickets by identity rather than knot id. The engine wakes on a shared-gate release while it has refused knots queued, not only on its own completions.
- `SubTapestry._run_inner(dispatcher=, concurrency=, admission_observers=)` and the overridable `_inner_dispatcher()` / `_inner_concurrency()` / `_inner_admission_observers()` hooks are the per-container overrides. `Engine._gate_for` is now public `Engine.gate_for`.

#### Per-item streaming from a fan-out (ADR agents-speaks-core, WS0b)

- `Emitter.on_knot_result(knot_id, result, lineage)` — a new no-op-default hook the engine awaits the moment a knot settles, inside the admission loop and before the knot's children are released, with the full `Ok` / `Err` / `Skipped` (the `Err`'s `ExceptionRecord` already re-registered against the run) and the `KnotLineage` row. Knots resolved without dispatch (skipped, missing parent) stream through it too. `EmitterFanout.emit_knot_result` delivers it under the run's `EmitterErrorPolicy`; an emitter without the method is skipped. `LineageRecorder.record_lineage` now returns the record it stashed.

#### Latest lineage by knot id (ADR agents-speaks-core, WS0b)

- `RunHistory.query_latest_lineage_by_knot_id(knot_id) -> KnotLineage | None` — the most recently finished lineage row for a stable knot id (by `finished_at`), on the base interface and the in-memory, SQLite, DuckDB and Postgres stores, pinned by the backend conformance suite. The keyed-identity lookup ("what did this knot last produce?") agents' memory recall and resume-after-crash key on.

#### pirn-agents on the WS0b seams

- `MapAgent` no longer assigns its inner tapestry's private `_concurrency` / `_dispatcher` / `_admission_observers` (`_apply_run_settings` is gone); it overrides `SubTapestry._inner_dispatcher` / `_inner_concurrency` / `_inner_admission_observers` instead, and `tests/core_seams/test_execution_plane_reach_through.py` ratchets the reach-through inventory at empty.
- `MapAgent.run()` yields each `BatchItemResult` the instant its item settles again (resumed items first, then completion order), via the new `_BatchItemStreamer` emitter over `Emitter.on_knot_result`; the streamed result carries the item's attempt count and latency from its lineage row. Closing the stream early or cancelling its consumer cancels the run.

#### `@tool` decorator and scalar auto-coercion

- `pirn/domains/agents/tool_decorator.py` — `@tool` decorator converts any sync or async function into a `FunctionTool` (a `Tool` subclass). Name is taken from the function name, description from the first docstring paragraph, and `parameters_schema` from type annotations. Both `Optional[T]` and `list[T]` annotations are handled. Import via `from pirn.domains.agents import tool, FunctionTool`.
- `pirn/core/knot.py` — Framework-level scalar auto-coercion: constructor parameters typed `Knot | T` (or `Union[Knot, T]`) now automatically wrap plain scalars in a `Parameter` node at construction time. The auto-created `Parameter` self-registers in the active `Tapestry` and participates in lineage tracking. Pydantic adapters for those parameters are built against `T` (not `Knot | T`) so validation works correctly at runtime.

#### LoopSubTapestry — iterative, feedback-driven sub-pipelines

`pirn/nodes/loop_sub_tapestry.py` — `LoopSubTapestry[S]` is a `SubTapestry` variant for pipelines where the number of steps is not known ahead of time: LLM agent loops, convergence-driven training, conversational turns. Implement two methods:

- `step(state: S) -> tuple[Tapestry, S] | None` — plan the next iteration or terminate.
- `fold(state: S, result: RunResult) -> S` — integrate an iteration's result into state.

Each iteration is registered as a real `_IterationChainKnot` in the inner tapestry's extensible run, making every step visible in run history and the explorer's drill-down. Zero-iteration loops (where `step` returns `None` immediately) are handled without exception. See `docs/guides/agentic-loops.md`.

#### Assembler / Disassembler pattern — Phases 1–5

Codifies and implements the bridge between pirn's connector layer (raw bytes / rows) and domain knots (typed `Payload` subclasses).

**Core:**
- `pirn/core/assembler.py` — thin `Assembler(Knot)` marker base class.
- `pirn/core/disassembler.py` — thin `Disassembler(Knot)` marker base class.
- `docs/contributing/assembler-disassembler-pattern.md` — convention reference.

**Signal domain:** `SignalObjectStoreAssembler`; `Signal/Spectrum/WaveletObjectStoreDisassembler`.  
**Oil & Gas domain:** `Las/Segy/ScadaDatabase/MudLog/WellCompletionObjectStoreAssembler`; `Las/SegyObjectStoreDisassembler`.  
**Health domain:** `Eeg/Meg/DicomPacs/WsiObjectStore/FhirPatientAssembler`; `Eeg/Meg/Dicom/WsiObjectStoreDisassembler`.  
**ML domain:** `TrainedModelObjectStoreAssembler`; `TrainedModel/Dataset/DataSplit ObjectStoreDisassembler`, `EvalReportDatabaseDisassembler`.

Eleven ingestor knots deleted (they collapsed I/O and assembly into one step, making them untestable and non-reusable): `AudioFileIngestor`, `LasFileIngester`, `SegyFileIngester`, `ScadaHistorianIngester`, `MudLoggingIngester`, `WellCompletionIngester`, `EEGRawIngestor`, `MegRawIngestor`, `DICOMIngestor`, `WsiTileExtractor`, `FhirPatientIngestor`.

#### Optional-dependency skip guards — 159 test files

All 159 unit test files that exercise optional-dependency code now wrap imports in `try/except ImportError as _e: raise unittest.SkipTest(...)` guards. Tests run against a minimal install (no optional deps) without collection errors; they run fully when deps are installed.

#### lance 1.x API migration

`pirn/domains/data/specialized/lance/` updated to the lance 1.x API:
- `arrow_to_lance_sink.py`: `from lance.dataset import write_dataset` (replaces `lance.write_dataset`).
- `lance_source.py`: `from lance.dataset import LanceDataset as _LanceDataset` (replaces `lance.dataset(path)` callable).
- `pyproject.toml`: `lance` optional extra corrected from `pylance>=0.18` (VS Code extension) to `lance>=1.0` (LanceDB library).

### Changed

#### Remaining engine-bypass sites closed (PIR-867)

The last standing entries in `tests/specializations/base/test_no_engine_bypass.py`'s bypass ratchet — `AWAITS_CHILD_PROCESS`, `LOOP_AWAITS_LLM_OR_TOOL_CALL`, and `USES_ASYNCIO_GATHER` — are now empty; `AWAITS_INVOKE` names a new sanctioned vending knot instead of the pipeline it used to flag. See `packages/pirn-core/docs/FRAMEWORK_REFERENCE.md` ("Control-flow vocabulary" and "Scheduling and concurrency") for the per-site detail.

- `retrieval/graph_rag/hybrid_graph_retriever.py::HybridGraphRetriever` wires its graph-traversal knot as a genuine upstream parent instead of awaiting its `process()` directly; its constructor no longer takes `store`/`budget`/`start_ids`/`direction`/`edge_types` — those now belong to the `GraphTraversal` knot passed in as `traversal=`.
- `_ChunkTranslator` and `FactClaimVerifier` fan independent per-item work (one chunk's translation, one claim's search) out into per-item knots joined by an `Aggregator`; `PlanExecutor` wires a `LoopSubTapestry` instead, since each step's prompt depends on every prior step's result. All three knots' `process()` now returns the sink of an inner pipeline rather than the computed value directly.
- `retrieval/hybrid_retriever.py::HybridRetriever` becomes a `SubTapestry` wiring its dense and lexical arms as two knots into an `Aggregator`, in place of a hand-rolled `asyncio.gather`. `specializations/document_processing/_chunk_embedder_store.py::_ChunkEmbedderStore` and `_ingestion_runner.py::_IngestionRunner` do the same for their per-chunk writes and per-document ETL; `_IngestionRunner`'s bounded concurrency is now a `ConcurrencyLimits` group cap (`_inner_concurrency()`) instead of a held `asyncio.Semaphore`.
- `specializations/multi_agent/orchestrator_workers.py::OrchestratorWorkers` and its internal `_WorkerInvocation` drop their own shared `asyncio.Semaphore` the same way — bounded concurrency is a `KnotConfig(concurrency_group=)` + `ConcurrencyLimits` group cap now, so the admission gate can see and steer it.
- `specializations/routing/_attempt_tier.py::_AttemptTier` no longer awaits `CascadeTier.invoke` directly: a new `_TierInvocation` knot makes the call, and `_TierAttemptFold` (`error_policy=RECEIVE_ERRORS`) folds its outcome into the cascade's state. `_AttemptTier` becomes an `AgentPipeline`. (PIR-872 then deleted `CascadeTier.invoke` and `_TierInvocation`: a tier is an `LLMChatCall` knot — see "Removed".)
- `rag/indexing/_raptor_assembler.py` keeps its atomic read-check-transform-write cycle unchanged (the assembler-disassembler ETL exception); giving each level's summarization its own lineage row via `SubTapestry._run_inner` was evaluated and deferred — see the module docstring for why it does not fit without a fragile multiple-inheritance workaround.

#### Specialization results, document loader, and PromptCache onto core seams (ADR agents-speaks-core WS6b, PIR-868)

- **`AgentResult` family onto `Payload[Frame, D]`.** The 11 specialization-pattern
  result types (`EvaluatorOptimizerResult`, `LatsResult`,
  `OrchestratorWorkersResult`, `WorkerTaskResult`, `PlanReActResult`,
  `PromptChainResult`, `SimulationResult`, `ReflexionResult`, `ReWooResult`,
  `FallbackResult`, `SelfAskResult`) are now `Payload[<Frame>, D]` instead of
  plain frozen-dataclass `AgentResult` subclasses, mirroring `AgentResponse`/
  `ConversationPayload` (WS6b): each gets a new `*Frame` type carrying the
  run-level facts (iterations, scores, candidate ids, budgets) and `D` carries
  the answer/content. `AgentResult` itself is now a thin generic `Payload`
  base. Pre-ADR field names stay available as read-only properties, so every
  existing construction and attribute-access call site keeps compiling
  unchanged; a structural `__eq__` on `AgentResult` preserves value-equality
  expectations dropped by no longer being a dataclass.
- **Document loader split.** `specializations/document_processing/_document_loader.py`
  (an "ingestor" reading files/HTTP directly inside `process()`) is deleted
  per `docs/contributing/assembler-disassembler-pattern.md` and replaced by
  `_DocumentSource` (a `Source` knot modeled on `ObjectStoreReadSource`: the
  guarded I/O, bytes out) and `_DocumentAssembler` (a `pirn.core.assembler.Assembler`:
  bytes in, no I/O, UTF-8 decode). `DocumentIngestionPipeline`'s public
  constructor is unchanged; every SSRF/path-traversal guard is preserved
  unchanged in behaviour (still delegated to `_DocumentSourceReader`).
- **`PromptCache` onto a core `DataStore`.** Entries move off a private
  `dict[str, CacheEntry]` onto a core `InMemoryDataStore` keyed by content
  hash, exactly like `SemanticResultCache`; the embedding index stays the
  plain `SimilarityIndex` resource. Because `DataStore` is async-only with no
  enumeration, `invalidate`/`purge_expired`/`__len__` are now
  `ainvalidate`/`apurge_expired`/`asize`; the previous synchronous names
  remain for one deprecation cycle as wrappers that bridge to the event loop
  (raising `RuntimeError` if called from inside one already running) and emit
  `DeprecationWarning`. The `max_entries` bound is now enforced by
  `InMemoryDataStore` (evicts the least-recently-*read* entry), not the
  previous first-inserted-wins policy.
#### Denied tool-call approval is `Skipped`, not `Err` (PIR-865)

A tool call whose `ToolPermissions.approval_required` is set and whose
`ApprovalHook` denies it now surfaces as a core `Skipped` all the way out —
the model is told the call was **skipped**, not that it failed.
`pirn_agents.agent.tool_approval_check.ToolApprovalCheck` (a core `Check`)
evaluates the same policy `ApprovalHook.authorize` always has, and
`ToolFactory.for_call` wires it behind a core `Gate` in front of the call
whenever the capability requires approval — the tool's own `process()` is
never invoked when the gate closes (behaviour-preserving for every
capability that does not require approval: nothing is wired for those at
all). Every execution site that builds a tool knot — `ToolFactory.for_call`
/ `run_call`, `ToolInvocation`, `ParallelToolExecutor`, `ParallelToolCaller`,
`ToolChain`, `ReActStepExecutor` — gained an `approval_hook` input threaded
through to `for_call`.

- **Breaking, by design:** a caller reading `ToolResult.status` for a denied
  call now sees the new `ToolStatus.SKIPPED` member instead of `ERROR`; the
  rendered message text also changed from `"skipped: <reason>"` to `"call
  skipped: <reason>"` (`"call skipped: approval denied"` specifically for a
  gated call, regardless of the engine's own generic propagation reason —
  see `ToolResult.from_result(..., gated=True)`). `ToolResult.to_result()`
  now round-trips a `SKIPPED` status back to a core `Skipped` instead of
  fabricating an `Err`.
- `ToolCallRejection` is unchanged and keeps its existing, narrower job: a
  call naming an unregistered tool, or whose arguments the declaration
  refuses, is still recorded as its own `Err` — that is a rejection, not an
  approval decision.
- Named `ToolApprovalCheck` rather than `ApprovalCheck`:
  `pirn_agents.specializations.human_in_the_loop.approval_check.ApprovalCheck`
  already holds that name for an unrelated seam (pausing a whole
  `AgentResponse` for human review).
- **Known limitation, deferred:** core's `Gate` always records
  `"gate_closed"` in its own lineage row, and the engine's parent-skip
  propagation always records `"parent_failed_or_skipped"` on the downstream
  tool knot's own row — neither is the literal string `"approval_denied"`
  in lineage. Rendering the accurate "approval denied" message to callers
  and the model does not depend on that (every call site can only reach a
  `Skipped` outcome via its own approval gate, so the label is always
  correct), but a reader of raw lineage rows still sees the engine's generic
  reason there. Giving `Gate`/`Check` a custom propagated skip reason is a
  core change, out of this ticket's scope.

#### `pirn-agents` hashing seams moved onto `pirn.core.hashing.content_hash` (ADR agents-speaks-core WS2 part 2)

`pirn_agents.builder.agent_knot_id_factory.AgentKnotIdFactory.derive` and
`pirn_agents.resilience.idempotency_key_assigner.IdempotencyKeyAssigner.assign`
now digest through `pirn.core.hashing.content_hash` instead of
`pirn_agents.serialization.canonical_json.CanonicalJson`. `content_hash` gained a
`strict=True` mode in the same change (raises `pirn.exceptions.unhashable_value_error.UnhashableValueError`
naming the innermost unhashable type instead of returning a best-effort sentinel).

- **Breaking, by design:** both outputs change value across the upgrade — the
  `sha256:`-prefixed digest `content_hash` emits IS the new format version, not
  an implementation detail.
- **`AgentKnotIdFactory.derive`** — acceptable at this package's current 0.x
  version: a generated knot id is a derived cache/lineage key, not data an
  operator persists across an upgrade boundary.
- **`IdempotencyKeyAssigner.assign`** — an operator-facing breaking change: an
  idempotency key sent to an external backend for retry dedup changes form, so
  **in-flight idempotent requests must be drained before/during the upgrade**
  or a retry that lands after it will double-apply. See "Idempotency keys"
  in `docs/domains/agents.md`.

#### Run-level and group concurrency limits (PIR-841, slice 2)

A run can now cap how many knots are in flight at once. `pirn/core/concurrency/concurrency_limits.py` adds `ConcurrencyLimits(max_in_flight=None, groups={})`, a frozen, serialisable value; limits are at least 1 and group names follow the knot id charset.

- **Where:** `RunRequest.concurrency` (per run) overrides `Tapestry(concurrency=...)` (default). `None` everywhere, or `ConcurrencyLimits()`, is unbounded, and uses the same lock-free gate as before.
- **Groups:** `KnotConfig(concurrency_group="openai")` puts a knot in a group; `ConcurrencyLimits(groups={"openai": 4})` lets at most four of them run at once, alongside any global cap. `concurrency_group` is excluded from `model_dump`, so `knot_config_hash` is unchanged and existing recordings still replay.
- **Undefined groups fail fast:** when the limits define any group, a knot in a group they do not define raises `UndefinedConcurrencyGroupError` (at run start, or at admission for a mid-run knot). Limits without groups ignore group tags. A defined group no knot uses emits `UnusedConcurrencyGroupWarning`.
- **Fairness:** `ReadyQueue` keeps one FIFO per group and a heap of group heads. A full group never blocks knots of other groups (no head-of-line blocking), and within a group knots start in readiness order. A full group is parked until its slot is released, so cost does not grow with the number of groups.
- **Serialisable:** `ConcurrencyLimits` (and a `RunRequest` carrying it) pickles and deep-copies; `groups` is a read-only `GroupLimits` mapping.
- **Known limitation:** `SubTapestry` / `LoopSubTapestry` hold one slot for their inner run's whole life until slice 3.
- **Slots always come back:** on success, failure, skip, cancellation and run abort. `pirn/engine/admission/limited_admission_gate.py` (`LimitedAdmissionGate`) refuses a double or foreign release with `AdmissionReleaseError`.
- **Unchanged under any limits:** outputs, lineage hashes, and the order of `lineage`, `exceptions`, `skipped` and `outputs`.
- **Not yet:** limits are not forwarded into `SubTapestry` / `LoopSubTapestry` inner runs (slice 3), and `Map` / `ZipMap` / `DictMap` elements are not admitted individually (slice 4).

#### Engine schedules knots through an admission queue (PIR-841, slice 1)

`pirn/engine/engine.py` no longer runs a graph in waves (dispatch every ready knot, wait for all of them, rescan for the next set). A knot now becomes ready the moment its own parents resolve and starts once the run's `AdmissionGate` admits it; the default `UnboundedAdmissionGate` admits everything, so no run is capped. New classes: `pirn/engine/scheduling/dependency_tracker.py` (`DependencyTracker`), `pirn/engine/scheduling/ready_queue.py` (`ReadyQueue`), and `pirn/engine/admission/` (`AdmissionGate`, `UnboundedAdmissionGate`, `AdmissionTicket`). There is no new public API yet.

- **Eager scheduling.** A child no longer waits for an unrelated slow sibling of its parent. Chains no longer pay an O(n²) ready-set rescan.
- **Unchanged:** outputs, every lineage hash, and the order of `RunResult.lineage`, `exceptions`, `skipped` and `outputs`. These are now sorted by `(level, dispatched, topological index)`, which reproduces the wave loop's order for any graph without mid-run registrations.
- **Changed order:** `RunResult.status_events` and live `on_status` delivery follow real transitions, so sibling knots' events interleave in the order the knots start and finish.
- **Fixed:** `KnotLineage.finished_at` is stamped when the knot finishes. Before, a fast knot listed after a slow sibling recorded the sibling's duration.
- **Mid-run extension:** registrations are merged each time a knot completes instead of between waves. A newcomer is ordered one level past the knot that registered it. A newcomer with no known registrar is reported after every knot with a known level, by registration sequence and then knot id. That covers registrations from a plain thread or external orchestrator, and every Postgres/ValKey delivery. This is a deliberate change from the wave loop, which placed such knots by whichever wave was running when they arrived.
- **Cancellation:** cancelling a run now cancels its in-flight knots, waits for their asyncio-side cleanup to finish, and raises `CancelledError` from `Tapestry.run`. Knots on worker threads are not interrupted. `streaming.run_stream` now re-raises that cancellation instead of passing it to `on_error`, matching `triggers.run_forever`. Before, the cancellation reached the one knot being awaited, `Knot.__call__` turned it into an `Err` (PIR-849), and the run returned a failed `RunResult`.

#### Agent control knots renamed

The four knots in `pirn/domains/agents/control/` were renamed to remove the misleading `Gate` suffix — `Gate` in pirn is a specific framework primitive (predicate pass-through → `Ok` or `Skipped`) and these knots do not extend it:

| Old name | New name |
|----------|----------|
| `SafetyGate` | `SafetyCheck` |
| `TerminationGate` | `TerminationCheck` |
| `ReflectionGate` | `ReflectionCheck` |
| `HandoffGate` | `HandoffCheck` |

Module paths updated accordingly (`safety_gate.py` → `safety_check.py`, etc.). The `ReActLoop`-internal `ReactTerminationGate` is similarly renamed to `ReactTerminationCheck`.

#### SubTapestry contract — `process()` returns `Knot`, not `RunResult`

`SubTapestry.process()` now returns the terminal `Knot` of the inner graph. The base class owns the `Tapestry()` context and calls `_run_inner` — subclasses must not open a `Tapestry()` context or call `_run_inner` directly. All existing SubTapestry subclasses (~90) have been migrated. The old contract raised `SubTapestryError` on inner failure; the new contract surfaces `Err` through the standard result chain.

Two new hooks on `SubTapestry` support specialised subclasses:
- `_extensible_inner_run: ClassVar[bool]` — when `True`, skips sink-registration validation and runs the inner tapestry in extensible mode.
- `_resolve_output_key(sink) -> str` — override to select which inner knot's output is surfaced as this SubTapestry's result.

---

### Removed

#### `pirn-agents` shadows of the core retry, timeout, nesting and check seams (PIR-872)

Deleted outright (no shims); every caller, test and doc moved in the same change.

| Removed | Replacement |
|---|---|
| `pirn_agents.llm.retry_policy.RetryPolicy` (`max_retries`, `backoff_delay`, `run`) | `pirn.core.knot_retry_policy.KnotRetryPolicy` — `KnotConfig(retry=)` on a knot, `KnotRetryPolicy.run(...)` below the knot boundary. `max_retries=n` is `max_attempts=n + 1`; the provider/embedding default `RetryPolicy()` is `KnotRetryPolicy(max_attempts=3)`. `BaseLLMProvider`/`HttpTransport`/`BaseEmbeddingProvider`/`HttpEmbeddingProvider`/`LocalEmbeddingProvider(retry_policy=)` and `IdempotentRetryPolicy(backoff=)` take a `KnotRetryPolicy`; the provider content identity names `max_attempts`. |
| `McpConnector(max_reconnect_attempts=, backoff_base=, backoff_cap=, jitter=)` | `McpConnector(reconnect=KnotRetryPolicy(max_attempts=5, base_delay=0.05, max_delay=2.0), rng=)` — the schedule is core's capped exponential backoff with full jitter (the additive-jitter formula is gone). |
| `pirn_agents.exceptions.tool_timeout_error.ToolTimeoutError` | `KnotConfig(timeout=)` → `Err(pirn.exceptions.knot_timeout_error.KnotTimeoutError)`. |
| `AgentRecursionError`, `AgentDepthExceededError`, `AgentCycleError` | `pirn.core.run_nesting.RunNesting` with `Tapestry(max_nesting_depth=)` → `NestingDepthExceededError` / `NestedRunCycleError`. |
| `pirn_agents.agent.agent_tool_context.AgentToolContext`, `current_agent_tool_context()`, `bind_agent_tool_context()` | Depth, run ids, path and cap: `RunNesting.current()`. The shared budget meter and pooled provider: `pirn_agents.agent.agent_tool_policy.AgentToolPolicy` (`meter`, `provider`, `bound()`/`current()`/`bind()`). |
| `pirn_agents.agent.agent_nesting_config.AgentNestingConfig` | The `max_depth=8` default on `AgentTool`/`AsTool.wrap`/`AgentAsToolMixin.as_tool`/`AgentToolCall`, applied as core's `max_nesting_depth`. |
| `pirn_agents.specializations.base.gated_agent_response.GatedAgentResponse` | A core `Check` and `Gate(input=value, check=verdict)` (see `_EvaluatorOptimizerLoop`'s `_CandidateRejectedCheck`); `AcceptCheck` is now a `Check`. |
| `CascadeTier.invoke` and `specializations/routing/_tier_invocation.py::_TierInvocation` | `CascadeTier(llm=LLMProvider)`: each tier runs as an `LLMChatCall` knot; `ModelCascadeRouter`'s `request` is the prompt string. |

`ParallelToolExecutor` keeps its public shape: each call is a tool knot with `KnotConfig(retry=, timeout=, concurrency_group="tools")` under an `Aggregator`, so core's `GovernedDispatch` owns the per-call backoff and timeout. The shadow and bypass ratchets (`tests/core_seams/test_core_seam_shadows.py`, `tests/specializations/base/test_no_engine_bypass.py`) are all `frozenset()` assertions now.

#### `pirn-agents` vocabulary onto core: outcomes, hashing, conventions (PIR-872)

Deleted outright (no shims, no aliases); every caller, test and doc moved in the same change.

| Removed | Replacement |
|---|---|
| `PromptCache.invalidate()`, `.purge_expired()`, `len(cache)` | `await cache.ainvalidate(...)`, `await cache.apurge_expired()`, `await cache.asize()`. |
| `pirn_agents.serialization.canonical_json.CanonicalJson`, `pirn_agents.serialization.opaque_policy.OpaquePolicy` (the whole `pirn_agents.serialization` package) | `pirn.core.content_hasher.ContentHasher.hash(value, strict=True)`; a type that needs a canonical form declares `__pirn_canonical__()`. `ContentDigest.digest` and `TrajectoryCallKey.args_key` now return core's `sha256:`-prefixed hash (cassette/trace keys and trajectory keys change value; neither is persisted across an upgrade). |
| `pirn_agents._internal._require._require` | `pirn_agents._internal.optional_import.OptionalImport.require`. |
| `ApprovalHook` module function `authorize_tool_call()` | `ApprovalHook.authorize()`. |
| `connector_lifespan()` | `ConnectorLifespan.manage()`. |
| `pirn_agents.tools.as_tool.as_tool()` | `AsTool.wrap()` (or `agent.as_tool()`). |
| `pirn_agents.tools.tool_decorator.tool` (`@tool`) | `ToolDecorator.decorate` (`@ToolDecorator.decorate`). |
| `reciprocal_rank_fusion()` | `ReciprocalRankFusion.fuse()`. |
| `decay_score()` | `DecayFunction.score()`. |
| `pirn_agents.testing.tool_test_harness.make_stub_tool`, `assert_tool_schema`, `assert_schema_shape`, `invoke_tool`, `collect_tool_stream` | `StubTool(...)`; `ToolTestHarness.assert_tool_schema`, `.assert_tool_schema_shape`, `.invoke_tool`, `.collect_tool_stream` (static methods). |
| `pirn_agents.tools.bundles.calculator_toolset`/`web_toolset`/`filesystem_toolset`/`data_toolset`/`retrieval_toolset`/`sandbox_toolset` | `Bundles.calculator_toolset()` … `Bundles.sandbox_toolset()`. |
| `pirn_agents.evaluation.eval_gate.EvalGate`, `evaluation.gate_result.GateResult` (not a core `Gate`) | `evaluation.eval_regression_check.EvalRegressionCheck`, `evaluation.eval_regression_verdict.EvalRegressionVerdict`. |
| `SQLAgent(read_only=)` / `_SQLExecutor(read_only=)` instance state | The class is the policy: `SQLAgent` is read-only; `specializations.specialized_agents.read_write_sql_agent.ReadWriteSQLAgent` (pattern `read_write_sql_agent`) may write. No upstream knot can flip it (PIR-817). |
| `specializations/multi_agent/_specialist_invoker.py::_SpecialistInvoker` | `specializations.multi_agent.specialist_handle.SpecialistHandle` — `SpecialistInvocation(specialist=SpecialistHandle(agent), ...)`, `_ReviewerInvocation(reviewer=SpecialistHandle(agent), ...)`, `await SpecialistHandle(agent).run(**inputs)`. |
| `MapAgent(run_item, ...)` positional form and its default `_config` | `MapAgent(run_item=..., _config=KnotConfig(id=...), ...)`; every setting is a declared knot input and is validated when the batch runs. |
| `DebateRoundFramer(**round_<i>=...)` | `DebateRoundFramer(prior_rounds=...)` — one declared input (an `Aggregator` over the prior rounds, or `()` for round 0). |
| `pirn_agents.batch.batch_item_status.BatchItemStatus`; `BatchItemResult(status=, output=, exception=)`, `.to_result()`, `.from_result()`, `.from_payload()` | `BatchItemResult(outcome=Ok \| Err \| Skipped)`; `succeeded`, `output`, `exception`, `error`, `timed_out` are derived; a resumed item is `Skipped(reason="resumed")`. |
| `BatchProgress.to_run_state()`, `.from_run_state()`, `.with_completed()`, `.with_all()`, `.from_payload()` | None — `BatchProgress` is a per-fire summary only; resume state is `RunHistory` lineage on `item:<batch_id>:<key>`. |
| `pirn_agents.tools.tool_status.ToolStatus`; `ToolResult(result=, error=, status=, exception=)`, `.to_result()` | `ToolResult(call_id=, outcome=Ok \| Err \| Skipped, latency=, tokens=)` (or `ToolResult.from_result(...)`); `result`, `error`, `exception`, `succeeded` and the model-facing `status` string (`"ok"`/`"error"`/`"timeout"`/`"skipped"`) are derived. An error-only view carries an `Err` record, so its text is `"<type>: <message>"`. `ToolResult.with_latency()` is new. |
| `pirn_agents.resilience.failover_outcome.FailoverOutcome` | `FailoverAttempt.result` (`Ok`/`Err`/`Skipped(reason=FailoverAttempt.circuit_open_reason)`); the trace dict carries `outcome` (`"ok"`/`"err"`/`"skipped"`) plus `error_type`. |
| `pirn_agents.resilience.retry_classification.RetryClassification`, `RetrySafetyClassifier.classify()` | `RetrySafetyClassifier.is_safe(error) -> bool` (a retry-safety verdict, not an outcome). |
| `pirn_agents.memory.stores.key_index_unreadable_error.KeyIndexUnreadableError` | None — its only raiser (`MemoryStoreKeyIndex`) was deleted in PIR-864. |
| `ResultCache.get()`/`.put()`/`.has()` (and the subclass overrides) | `cache.get_or_compute(payload, compute)`; raw keyed access is `cache.store` (the core `DataStore`). |
| `pirn_agents.caching.vector_memo_index.VectorMemoIndex` | `EmbeddingCache` stores vectors in a core `InMemoryDataStore`; `EmbeddingCache.invalidate()` is now a coroutine. |

Also changed: `BudgetBreachError`, `StructuredDecodeError`, `SpecialistInvocationError`, `ConstitutionalViolationError`, `McpError`, `PromptRenderError`, `CircuitOpenError`, `LLMProviderError` and `RateLimitSignal` subclass `pirn.exceptions.pirn_error.PirnError` (keeping their builtin base); `TokenBucketRateLimiter` and `AdaptiveConcurrencyController` mix in `PirnOpaqueValue`; the `Retriever`/`Router`/`Writer`/`AgentPipeline` `process()` catch-alls are `**_`. The agents conventions baseline is 0 in every category, and the vocabulary ratchets (`EXCEPTION_ROOTS_WITHOUT_PIRN_ERROR`, `CANONICAL_JSON_IMPORTERS`, `OUTCOME_ENUMS_BESIDE_RESULT`, `PARALLEL_VOCABULARY_IMPORTERS`, `CHECKPOINTS_OUTSIDE_RUN_HISTORY`, `LIFECYCLE_IMPORTERS`) are empty; the keyed-store and structural-type ratchets are now named design inventories with a reason per entry.

#### Core deletions and module-level functions folded into classes (PIR-872)

pirn is alpha: a replaced name is deleted in the same change, never deprecated
(`docs/guides/versioning.md`). Apply this table when upgrading.

| Removed | Use instead |
|---|---|
| `pirn.emitters.base` / `pirn.triggers.base` / `pirn.streaming.base` (module shims) | `pirn.emitters.emitter.Emitter`, `pirn.triggers.trigger.Trigger`, `pirn.streaming.streaming_source.StreamingSource` |
| `pirn.domains.*` import shim (`pirn/domains/`, `DomainCompatFinder`/loader) | `import pirn_<domain>` (`pirn_data`, `pirn_ml`, `pirn_signal`, `pirn_agents`, `pirn_health`, `pirn_oilgas`) |
| `pirn-migrate-imports` console script and `pirn._migrate` | rewrite `pirn.domains.<x>` to `pirn_<x>` directly |
| `Knot._deprecated_since`, `Knot._deprecation_notice` | — (no construction-warning seam; a replaced knot is deleted) |
| `pirn_data.specializations.scd.scd_type_1_overwrite.ScdType1Overwrite` | `pirn_data.specializations.incremental.merge_upsert.MergeUpsert` |
| `pirn.core.hashing.content_hash` (and the `pirn.core.hashing` module) | `pirn.core.content_hasher.ContentHasher.hash` |
| `pirn.yaml_loader.pipeline_loader.load_pipeline` | `PipelineLoader.load_yaml` |
| `pirn.engine.shed.shed.detect_cycle` | `pirn.engine.shed.cycle_detector.CycleDetector.detect` |
| `pirn.check.validator.validate_tapestry` (and the `pirn.check.validator` module) | `pirn.check.tapestry_validator.TapestryValidator.validate` |
| `pirn.managers.redact.redact_common_secrets` (and the `pirn.managers.redact` module) | `pirn.managers.traceback_redactor.TracebackRedactor.redact_common_secrets` |
| `pirn.nodes.continuation.continues` | `pirn.nodes.with_continuation.WithContinuation.attach` |
| `pirn.connectors.connection_config_decorator.connection_config` | `@ConnectionConfigDecorator.apply` |
| `pirn.core.async_callable.is_async_callable` | `AsyncCallable.is_async_callable` |
| `pirn.core.knot_source_record.extract_knot_source` | `KnotSourceRecord.from_knot` |
| `pirn.knot_diff.replay_run` / `compare_runs` | `KnotDiff.replay_run` / `KnotDiff.compare_runs` |
| `pirn.engine.dispatchers.celery_dispatcher.register_celery_worker_task` | `CeleryDispatcher.register_worker_task` |
| `pirn.tapestry.current_emitters` / `current_emitter_error_policy` | `Tapestry.current_emitters()` / `Tapestry.current_emitter_error_policy()` |
| `pirn.viz.tapestry_html_renderer.html_for_tapestry` / `html_for_run` | `TapestryHtmlRenderer.for_tapestry` / `TapestryHtmlRenderer.for_run` |
| `pirn.viz.mermaid_renderer.mermaid_for_tapestry` / `mermaid_for_run` | `MermaidRenderer.for_tapestry` / `MermaidRenderer.for_run` |
| `pirn.viz.tapestry_graph_scanner.scan_folder` | `TapestryGraphScanner.scan` |
| `pirn.viz.explorer_html_generator.generate_explorer_html` | `ExplorerHtmlGenerator.generate` |
| `pirn.tapestry.get_current_store()` | `Tapestry.current_store()` |
| `pirn.tapestry.current_tapestry()` | `Tapestry.current()` |
| `pirn.tapestry.current_run_id()` | `Tapestry.current_run_id()` |
| `pirn.domain_discovery.discover_installed_domains()` | `DomainDiscovery.discover_installed_domains()` |
| `pirn.triggers.trigger.run_forever(trigger, tapestry, ...)` | `trigger.run_forever(tapestry, ...)` |
| `pirn.streaming.streaming_source.run_stream(source, tapestry, ...)` | `source.run_stream(tapestry, ...)` |
| `@pirn.core.knot_factory.knot` / `knot(fn)` | `@KnotFactory.knot` / `KnotFactory.knot(fn)` |

#### Renamed (PIR-872)

| Old | New |
|---|---|
| `pirn.engine.admission.admission_gate.AdmissionGate` | `pirn.engine.admission.admission.Admission` |
| `pirn.engine.admission.limited_admission_gate.LimitedAdmissionGate` | `pirn.engine.admission.limited_admission.LimitedAdmission` |
| `pirn.engine.admission.unbounded_admission_gate.UnboundedAdmissionGate` | `pirn.engine.admission.unbounded_admission.UnboundedAdmission` |
| `pirn.nodes.continuation` (module) | `pirn.nodes.with_continuation` |
| `pirn.core._content_hasher._ContentHasher` | `pirn.core.content_hasher.ContentHasher` |
| `pirn.managers.redact._TracebackRedactor` | `pirn.managers.traceback_redactor.TracebackRedactor` |
| `pirn.check.validator._TapestryValidator` | `pirn.check.tapestry_validator.TapestryValidator` |
| `pirn.domain_discovery._DomainDiscovery` | `pirn.domain_discovery.DomainDiscovery` |
| `InMemoryDataStore.DEFAULT_MAX_VALUES` | `InMemoryDataStore.default_max_values` |
| `InMemoryHistory.DEFAULT_MAX_RUNS` | `InMemoryHistory.default_max_runs` |
| `InvocationIdentity.UNCOMPARABLE_MARKER` | `InvocationIdentity.uncomparable_marker` |

`Knot.process` and `SubTapestry.process` declare their catch-all as `**_`, and
the conventions gate no longer applies the knot-subclass rules to pirn-core's
own definition of a framework root (`Knot`, `Aggregator`, …); every subclass is
still checked.

#### Names superseded by the ADR "agents speaks core" (PIR-864)

Every public name below was replaced by an ADR "agents speaks core" workstream and is deleted outright. Each entry names its replacement.

**Tool / agents (WS1):**
- `Tool.invoke()` and the invoke-shaped `Tool` subclass path (`Tool.__init_subclass__`'s legacy detection, `_legacy_tool`/`_legacy_init`/`_legacy_factory`/`_legacy_declaration`) — construct the tool knot and run it in a `Tapestry`, or `ToolFactory.for_call(call)`.
- `ToolFactory.invoke()`, `ToolFactory.as_tool_result()`, `ToolFactory.from_legacy()` — run the call as a knot and read its `Result`; `ToolResult.from_result()` builds the view.
- `BaseTool` — subclass `Tool` directly.
- `ToolSchemaCompiler` — `Tool.declaration()` / `ToolFactory.declaration()` (backed by `Knot.input_json_schema()`).
- `ArgumentValidator` (and the now-empty `pirn_agents.validation` subpackage) — `ToolFactory.validate_arguments()`.
- `AgentSchemaDeriver` — `AgentTool(agent).declaration().parameters`.
- `AgentInvoker` — wrap the agent with `AgentTool` and run the call as a knot.
- `ToolInvocationHook` (and `ParallelToolExecutor`'s `hook=`/`retries=`/`retry_policy=`/`rng=`/`sleep=` constructor kwargs) — observe a call through its `KnotLineage` row and the run's emitters; `retry=KnotRetryPolicy(max_attempts=...)` for retries.
- `_FanoutRunner`, `AsyncFanoutEngine` — one knot per item under a core `Aggregator`; per-item timeout/retry via `KnotConfig.timeout`/`KnotConfig.retry`.
- `AgentTool.invoke()` — `AgentTool.for_call(call)` run as a knot, or `run_view()`.

`ToolResult` was **not** removed: PIR-865 (#348) gave `ToolResult.from_result(gated=)` a live role rendering gated/approval outcomes to the model (PIR-872 later deleted `ToolStatus`; see above).

**Observability (WS4a):**
- `Tracer`, `OtelSink`, `LoggingSink`, `SpanEmittingToolInvocationHook`, `Span`, `SpanKind`, `SpanStatus`, `OpenSpanEntry`, `ObservabilitySink` — `AgentCallRecorder.record(...)` emits a core `StatusEvent` through the run's own emitters (`OpenTelemetryEmitter`, `LogEmitter`, or any custom `Emitter`); no separate sink or hook to build.

**Sessions / determinism (WS3):**
- `RunCheckpoint`, `RunCheckpointer`, `SessionStore`, `InMemorySessionStore`, `PersistedSessionStore`, `ThreadRepository`, `MemoryStoreKeyIndex` — a session is a chain of engine runs (`SessionChain`); `RunState.from_chain()` projects the read model; `ConversationThread` persists multi-turn history over core's own `DataStore`/`RunHistory`.
- `CassetteStore`, `InMemoryCassetteStore`, `FileCassetteStore` — `CassetteRecorder` records to and replays from `RunHistory`/`DataStore` directly.
- `TrajectoryRecorder` — a `TrajectoryEmitter` attached to a `Tapestry` captures every knot's lineage via `on_lineage` automatically.

**Batch (WS4b):**
- `BatchScheduler`, `BatchCheckpointer` — `MapAgent` resumes from a `RunHistory` lineage query on the item's knot id; pass `history=`/`data_store=`.

`BatchProgress` was **not** removed: `TriggeredBatch`'s `run()` returns it as its per-fire summary (PIR-872 reduced it to a pure summary; see above).

**Concurrency (WS4b/PIR-866):**
- `BackpressureSemaphore`, `Bulkhead`, `ConcurrencyConfig`, `BulkheadConfig` (and their private `_backpressure_admission`/`_admission_slot_knot` implementation) — declare `KnotConfig(concurrency_group=<backend>)` on the knots that call a backend and `ConcurrencyLimits(groups={<backend>: n})` on the run; every knot in that group is metered together by one shared `Admission`. `agent/parallel_tool_executor.py` and three `specializations/` pipelines (`document_processing/ingestion_pipeline.py`, `multi_agent/orchestrator_workers.py`, `rewoo/rewoo_pipeline.py`) that read `ConcurrencyConfig.max_concurrency` as a class-level default now default to a plain literal `8`. `evaluation/run_eval.py::RunEval.run` — the one caller with no `Tapestry` to attach a group to — now bounds its per-item concurrency with a plain `asyncio.Semaphore(concurrency)` (`concurrency` is a plain `int`, default 8) instead.

**Naming (`*Gate` → `*Check`, Knot Design Rule 7):**
- `FactCheckGate`, `InputGuardrailGate`, `OutputGuardrailGate`, `AcceptGate` (pirn-agents), `ChampionChallengerGate` (pirn-ml), `SeismicQCGate` (pirn-oilgas), `ClinicalDataQualityGate`, `GenomicsQCGate` (pirn-health) — construct `FactCheck`, `InputGuardrailCheck`, `OutputGuardrailCheck`, `AcceptCheck`, `ChampionChallengerCheck`, `SeismicQCCheck`, `ClinicalDataQualityCheck`, `GenomicsQCCheck` respectively.

**Miscellaneous:**
- `ResolvedValueKnot` (WS5a) — construct `pirn.core.parameter.Parameter` directly.
- `MessagesPassthrough` (WS5a/WS5b) — `Parameter("seed_messages", tuple[AgentMessage, ...], default=..., ...)` for the constant-seed case (the class's other call shape, an upstream `Knot`, had no in-tree or external caller).
- `ConsensusAggregator` (WS5b) — `ConsensusPipeline`.
- `AgentContext` (WS6b) — `ConversationPayload` (its `extra=` kwarg replaces `AgentContext`'s `metadata`).
- `ContentAddress`, `content_address()` (WS2) — `ContentHasher.hash(value, strict=True)` (`pirn.core.content_hasher`) directly.
- `IdempotencyKeyAssigner.legacy_key()` (WS2 part 2) — `IdempotencyKeyAssigner.assign()` (already the default derivation).
- `AgentSpecLoader`'s legacy flat-dict dialect (WS6a) — `AgentSpecLoader.from_mapping`/`from_json`/`from_yaml`/`from_path` now accept only a core pipeline document (a top-level `nodes:` list); `AgentSpecLoader.to_json`/`to_yaml` now write that same shape (previously the flat dict) so read/write keep round-tripping. `AgentSpec.from_dict()`/`.to_dict()` are unaffected — they still construct/serialise the flat shape directly for a caller that already has one.

**Module-level functions folded into their class (PIR-869 follow-through):**
- `pirn_agents.evaluation.run_eval:run_eval` — `RunEval.run(...)` (already the implementation; the free function was a thin wrapper).
- `pirn_agents.specializations.structured_output.structured_decoder:structured_decode` — `StructuredDecoder.decode_once(...)` (already the implementation).

**Deferred, not removed in this release:** `CanonicalJson` and `OpaquePolicy` are still imported by `determinism/content_digest.py` and `evaluation/trajectory_call_key.py` (both non-durable, in-memory-only per their own module docstrings); retiring those two callers is a decision for whichever lane owns `CanonicalJson`'s eventual retirement, not made unilaterally here. `IdempotencyKeyAssigner.legacy_key()` (the only other caller) is deleted above.

---

### Added (prior)

#### Agentic design patterns guide

`pirn/domains/agents/PATTERNS.md` — a comprehensive reference covering 18 agentic and multi-agentic design patterns with real knot wiring examples: single agent, ReAct loop, planner/router/executor, generator+critic, coordinator/dispatcher, parallel fan-out/gather, synthesiser, hierarchical decomposition, blackboard (MAS shared state), supervision (guardrail stacking), debate framework, four memory patterns, four RAG variants, structured output extraction, specialised agents, agent-as-tool, MCP usage, and swarm (decentralised multi-agent). Every entry maps to the concrete `pirn.domains.agents` knot that implements it.

#### New examples

Seven domain-format examples added to `examples/domain_formats/`:

- **`medical_triage_agent.py`** — Dynamic DAG over a synthetic DICOM study queue; windowing, tissue classification, and anomaly detection knots run concurrently per study; triage decisions route the next study or terminate. Record schema matches `DicomFormat.decode()`.
- **`seismic_survey_pipeline.py`** — SEG-Y trace QC and attribute extraction pipeline; parallel frequency analysis and amplitude QC converge into survey reports. Schema matches `SegyFormat`.
- **`weather_forecast_pipeline.py`** — Synthetic GRIB ensemble pipeline; surface parameter extraction, alert checking, and forecast report assembly. Schema matches `GribFormat`.
- **`ml_evaluation_loop.py`** — Dynamic evaluation loop that registers a benchmark suite (accuracy, latency, memory) per model candidate and promotes or rejects each.
- **`geospatial_layer_analysis.py`** — Site suitability scoring over synthetic GeoJSON/Shapefile layers; four spatial analysis knots run in parallel per site.
- **`hl7v2_message_router.py`** — HL7 v2 message routing pipeline; type-specific handler knots with PHI scrubbing aligned to `Hl7v2Format`.
- **`genomics_batch_qc.py`** — FASTQ sequencing run QC; quality trimming, alignment simulation, and metric assembly. Schema matches `FastqFormat`.

`examples/llm_agent/agent_loop_v2.py` — Rewritten to use real `pirn.domains.agents` composites. The dynamic DAG shell is identical to `agent_loop.py`; action knots now use `ContextBuilder → LLMCall → OutputParser` (`llm_task`), `ReActLoop` (`react`), and `ContextBuilder → Planner → ToolRouter → ToolExecutor` (`planner`). `StubLLMProvider` and `StubTool` satisfy the interfaces without network access.

### Fixed

#### SQLiteHistory bytes and datetime serialization

`SQLiteHistory.record_run()` previously called `model.model_dump_json()` directly, which hard-fails on pydantic models containing `bytes` fields (encoding error) or bare `datetime` objects (not JSON-serialisable). Replaced with `_model_to_json(model)` — a thin wrapper over `json.dumps(model.model_dump(mode="python"), default=_json_default)` where `_json_default` encodes `bytes` as `{"__bytes_b64__": "<base64>"}`, `datetime`/`date` objects via `.isoformat()`, and dataclasses via `dataclasses.asdict()`. All example pipelines including those with binary-payload formats (DICOM, SEG-Y, GRIB) now persist run history correctly without per-pipeline workarounds.

#### Domain libraries (Phase 4)

Six domain-specific knot libraries are now available under `pirn/domains/`, each isolated behind its own optional extra:

- **`pirn[data]`** — tiered data-frame knots (Tier 1 dict batches, Tier 2 pandas/Polars/DuckDB/DataFusion, Tier 2.5 Modin, Tier 3 Ibis/Spark/Dask/Ray, Tier 4 Lance/Eland), plus tabular transform knots, validation integrations (Pandera, Great Expectations), and quality gates.
- **`pirn[agents]`** — LLM-backed knots, tool use, memory stores, planning, control gates, RAG, ReAct, multi-agent coordination, structured output extraction, and document processing pipelines.
- **`pirn[ml]`** — data prep, feature engineering, training, evaluation, deployment, shadow deployers, drift monitors, lineage tracking, and pre-built task pipelines (classification, regression, forecasting, NLP, computer vision).
- **`pirn[health]`** — DICOM, FHIR R4/R5, HL7v2, EDF/BDF, CDA, NIfTI/NIfTI2, FASTA, FASTQ, VCF, BCF connectors with PHI redaction and genomics processing knots.
- **`pirn[signal]`** — time-series transforms, DSP knots (FFT, filtering, windowing), audio format connectors (WAV, FLAC, MP3/Ogg, AIFF), and wavelet processing via PyWavelets.
- **`pirn[oilgas]`** — SEG-Y seismic, LAS well-log, and WITSML connectors; trace/header extraction and depth-log transform knots.

#### File format connectors — approximately 98 formats across 16 categories

**Wave 1 — Universal tabular formats (pirn/domains/connectors/file_formats/)**
- CSV, JSON, NDJSON, TSV, XML — streaming line-by-line row encoders/decoders
- Parquet, ORC, Avro, Feather — columnar binary formats via PyArrow/fastavro

**Wave 2 — Compression codecs (pirn/domains/connectors/file_formats/codecs/)**
- `GzipFormat`, `Bzip2Format` — stdlib; no extra required
- `ZstdFormat` (`pirn[zstd]`), `SnappyFormat` (`pirn[snappy]`), `Lz4Format` (`pirn[lz4]`)
- `CompressedFileFormat` — wraps any `StreamingFileFormat` with any codec

**Wave 2 — Archive formats**
- `TarFormat`, `ZipFormat` — streaming member extraction with zip-slip path-traversal protection

**Wave 2 — Lakehouse table formats**
- `DeltaFormat` (`pirn[delta]`) — Delta Lake read/write via `deltalake`
- `IcebergFormat` (`pirn[iceberg]`) — Apache Iceberg read via `pyiceberg`
- `HudiFormat` (`pirn[hudi]`) — Apache Hudi read via PyArrow (write path requires Spark/Java writer; Python write is not yet stable)

**Wave 3 — Office and document formats**
- `XlsxFormat` (`pirn[xlsx]`), `OdsFormat` (`pirn[ods]`) — spreadsheets
- `DocxFormat` (`pirn[docx]`), `PptxFormat` (`pirn[pptx]`) — Word/PowerPoint
- `PdfFormat` (`pirn[pdf]`) — read via pypdf, write via reportlab
- `RtfFormat` (`pirn[rtf]`), `EpubFormat` (`pirn[epub]`) — rich text / e-books
- `HtmlFormat` (`pirn[html]`), `MarkdownFormat` (`pirn[markdown]`) — markup

**Wave 3 — Scientific / multidimensional formats**
- `Hdf5Format` (`pirn[hdf5]`) — HDF5 dataset/group/attribute access via h5py
- `NetcdfFormat` (`pirn[netcdf]`) — NetCDF-4 via netCDF4
- `ZarrFormat` (`pirn[zarr]`) — chunked array stores
- `MatlabFormat` (`pirn[matlab]`) — MATLAB `.mat` files via SciPy

**Wave 3 — Image formats**
- `ImageFormat` (`pirn[image]`) — PNG, JPEG, WebP via Pillow
- `TiffFormat` (`pirn[tiff]`) — multi-page TIFF via tifffile + Pillow
- `HeicFormat` (`pirn[heic]`) — HEIC/HEIF via pillow-heif

**Wave 3 — Geospatial formats**
- `GeoJsonFormat` (`pirn[geojson]`), `ShapefileFormat` (`pirn[shapefile]`)
- `KmlFormat` (`pirn[kml]`), `GeoTiffFormat` (`pirn[geotiff]`), `GeoPackageFormat` (`pirn[geopackage]`)

**Wave 3 — ML artifact formats**
- `OnnxFormat` (`pirn[onnx]`) — whole-model protobuf with optional `onnx.checker` validation
- `SafetensorsFormat` (`pirn[safetensors]`) — RCE-safe Hugging Face tensor storage
- `JoblibFormat` (`pirn[joblib]`) — joblib/pickle with mandatory signer or explicit `allow_unsigned` acknowledgement
- `PytorchFormat` (`pirn[pytorch]`) — PyTorch state dicts; defaults `weights_only=True`; full-model loading requires signer
- `TfSavedModelFormat` (`pirn[tensorflow]`) — SavedModel directory bundled as ZIP
- `GgufFormat` (`pirn[gguf]`) — llama.cpp quantised LLM weights
- `TfliteFormat` (`pirn[tflite]`) — TFLite FlatBuffer models

**Wave 4 — Healthcare formats (pirn/domains/connectors/file_formats/healthcare/)**
- `DicomFormat` (`pirn[health]`) — DICOM image/RT/SR with built-in PHI redaction
- `FhirFormat` (`pirn[health]`) — FHIR R4/R5 JSON bundles via fhir.resources
- `Hl7v2Format` (`pirn[health]`) — HL7v2 ADT/ORM/ORU pipe-encoded messages with PHI tag stripping
- `EdfFormat` (`pirn[health]`) — EDF/BDF physiological signal files via pyedflib; PHI-bearing header fields scrubbed on request
- `CdaFormat` (`pirn[health]`) — CDA R2 XML clinical documents with configurable PHI tag redaction
- `NiftiFormat` (`pirn[health]`) — NIfTI-1 and NIfTI-2 neuroimaging via nibabel; BIDS companion sidecar support; zip-slip-safe BIDS archive extraction

**Wave 4 — Genomics formats**
- `FastaFormat` (`pirn[genomics]`) — FASTA sequence files via pyfaidx
- `FastqFormat` (`pirn[genomics]`) — FASTQ read files with quality score parsing
- `VcfFormat` (`pirn[genomics]`) — VCF variant call files via pysam
- `BcfFormat` (`pirn[genomics]`) — BCF binary variant files via pysam

#### Convenience aggregate extras

- `pirn[all-frames]` — all Tier-2 single-machine CPU frame engines (polars, pandas, pyarrow, duckdb, datafusion)
- `pirn[all-lazy]` — all Tier-3 push-down/lazy engines (ibis, pyspark, ray[data], dask)
- `pirn[all-domains]` — all domain library dependencies
- `pirn[all-db]`, `pirn[all-storage]`, `pirn[all-stream]`, `pirn[all-saas]`, `pirn[all-observability]` — groupings for connector categories

#### Documentation

- `docs/domains/agents.md` — agents domain reference: interfaces, sub-packages, code examples
- `docs/domains/ml.md` — ML domain reference: artifact formats with security properties, providers, sub-packages, code examples
- Domain libraries section added to README
- CHANGELOG introduced (this file)

### Security

- **PHI redaction** — DICOM, FHIR, HL7v2, EDF/BDF, and CDA format connectors include configurable PHI-field scrubbing. Redaction events are content-addressed through pirn's lineage layer so every scrub is auditable.
- **ML deserialization guards** — `JoblibFormat` and `PytorchFormat` constructors refuse unsigned construction. Production use requires a `_Signer` (HMAC-SHA256 signs before emission; verifies before load). Dev/test must explicitly pass `allow_unsigned=True`.
- **Zip-slip protection** — `ZipFormat`, `TarFormat`, `TfSavedModelFormat`, and `NiftiFormat` (BIDS archive extraction) guard against absolute and parent-directory member paths.
- **`weights_only=True` default** — `PytorchFormat` defaults to PyTorch's safe-mode loader, which restores tensor data only and refuses arbitrary callables.

### Fixed

- Removed module-level constants from domain connector files; moved to class-level or instance attributes per SOLID conventions.
- Removed nested function definitions from connector encode/decode paths.
- Replaced `Protocol` usage with explicit interface base classes (`LLMProvider`, `Tool`, `MemoryStore`, `EmbeddingProvider`, `FeatureStoreProvider`, `ImageEncoderProvider`, `LineageStore`) in line with pirn's one-class-per-file, interface-not-Protocol convention.
- Enforced one class per file throughout `pirn/domains/`.
- Corrected import ordering (stdlib → third-party → pirn-internal) in newly added modules.
- Suppressed `pyright` `reportMissingImports` for optional heavy extras (onnx, torch, tensorflow, etc.) that are imported lazily.

---

[Unreleased]: https://github.com/snoodleboot-io/pirn/compare/v0.3.0...HEAD
