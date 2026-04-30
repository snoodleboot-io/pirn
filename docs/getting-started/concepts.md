# Concepts

Glossary of every term in the pirn framework. Each term is defined concisely; follow the "see also" links for implementation details.

---

## Knot

The fundamental unit of work. A knot is a typed, async function with explicit input and output declarations. It has exactly one output type and zero-or-more named inputs. Inputs can come from other knots (parents) or from static config values.

Knots are immutable after construction — you cannot change a knot's parents or config once it has been built. This makes pipelines safe to reason about statically.

```python
from pirn import knot

@knot
async def score(text: str, threshold: float) -> float:
    return sentiment_model(text)
```

**See also:** [API — Core](../api/core.md), [Architecture — Knot Lifecycle](../architecture/overview.md#knot-lifecycle)

---

## Tapestry

The workspace that holds a collection of knots and drives their execution. You build knots inside a `with Tapestry() as t:` block — the context variable auto-registers each knot. Calling `t.run(request)` walks the registered knots, builds the execution graph, and runs everything in topological order.

A tapestry holds three backend slots: `TapestryStore`, `RunHistory`, and `DataStore`. These default to in-memory implementations and can be swapped to durable backends independently.

**See also:** [API — Tapestry](../api/tapestry.md), [Backends](../guides/backends.md)

---

## Shed

The per-run, ephemeral subgraph built from a set of terminal knots by BFS traversal. The shed is an internal engine concept — you never interact with it directly. It contains:

- `knots` — all reachable knots by id.
- `edges_by_child` — parent edges for each knot.
- `children_by_parent` — child ids for each parent.

The shed also runs a cycle check (raises `ShedError` if a cycle is found) and computes topological order via Kahn's algorithm.

**See also:** [Architecture — Execution Model](../architecture/execution-model.md)

---

## Lineage

The audit trail produced by every run. Each knot execution produces a `KnotLineage` record that captures: what it received (parent input hashes), what it produced (output hash), when it ran, and how (which dispatcher). Because values are content-addressed by `sha256`, identical values in different runs produce the same hash, enabling cross-run comparisons without extra infrastructure.

```python
record = result.lineage[0]
print(record.output_hash)      # sha256:abc123...
print(record.parent_input_hashes)  # {"x": "sha256:def456..."}
```

**See also:** [Architecture — Content-Addressed Lineage](../architecture/overview.md#content-addressed-lineage), [API — Core](../api/core.md)

---

## Thread (edge)

In the weaving metaphor, a thread is the dependency edge between two knots — the connection from a parent knot's output to a child knot's input. Internally, edges are represented as `Edge(child_id, parent_id, name)` Pydantic models in the shed.

You create threads implicitly: pass one knot as a kwarg to another's constructor.

---

## Loom (graph)

The full dependency graph of all knots in a tapestry — the "loom" on which the threads are woven. pirn doesn't expose a separate "graph" object; the loom is implicit in the knot/parent relationships stored in the tapestry's `TapestryStore`.

---

## Parameter

A special knot with no parents that binds an external value at run time. Parameters are the entry points for data into a tapestry.

```python
from pirn import Parameter

x = Parameter("x", int)               # id="x", type=int, no default
y = Parameter("y", float, default=1.0)  # optional parameter with default
```

The id of a parameter knot is what you use in `RunRequest.parameters`.

**See also:** [API — Core](../api/core.md)

---

## Ok / Err / Skipped

The three-way result type that every knot produces:

| Variant | Meaning |
|---------|---------|
| `Ok(value)` | Knot ran successfully; `value` is the typed output. |
| `Err(record)` | Knot raised an exception; `record` is an `ExceptionRecord`. |
| `Skipped(reason)` | Knot was deliberately not run. |

`Skipped` is distinct from `Err` — "didn't run because the gate was closed" is different from "crashed". Downstream knots and emitters can react differently to each.

**See also:** [Error Handling](../guides/error-handling.md), [API — Core](../api/core.md)

---

## Dispatcher

The component that decides *where* a knot runs. The dispatcher implements a simple two-method protocol: `name` (string) and `async dispatch(knot, inputs) -> Result`.

Built-in dispatchers:

| Dispatcher | Where it runs |
|------------|--------------|
| `LocalDispatcher` | Current event loop (default) |
| `ThreadDispatcher` | Global thread pool (`ThreadPoolExecutor`) |
| `CeleryDispatcher` | Celery worker processes |
| `DaskDispatcher` | Dask cluster |
| `RayDispatcher` | Ray cluster |

**See also:** [Backends](../guides/backends.md), [API — Dispatchers](../api/dispatchers.md)

---

## Emitter

An observer that receives events during a run. Emitters implement three async hooks:

- `on_status(event)` — fires on each knot state transition (RUNNING → SUCCEEDED/FAILED/SKIPPED).
- `on_lineage(record)` — fires once per knot, after it completes.
- `on_run_result(result)` — fires once per run, after `history.record_run()`.

A broken emitter never breaks a run — exceptions inside emitters are isolated.

**See also:** [Observability](../guides/observability.md), [API — Emitters](../api/emitters.md)

---

## Trigger

A source of `RunRequest` objects that starts a new pipeline run for each external event. Triggers implement `name`, `stream() -> AsyncIterator[RunRequest]`, and `close()`.

Drive a trigger with `run_forever(trigger, tapestry)`.

Built-in triggers: `CronTrigger`, `WebhookTrigger` (HTTP), `KafkaTrigger`, `ValkeyTrigger`.

**See also:** [API — Triggers](../api/triggers.md), [Observability](../guides/observability.md)

---

## RunRequest

The input to a single pipeline execution. Contains `parameters` (a `dict[str, Any]` mapping parameter ids to values) and a `run_id` (auto-generated UUID if omitted).

```python
from pirn import RunRequest

request = RunRequest(parameters={"user_id": "u123", "threshold": 0.7})
```

---

## RunResult

The output of a single pipeline execution. Contains:

- `outputs` — `dict[str, Any]` of raw values for `Ok` knots.
- `lineage` — `list[KnotLineage]`, one per knot.
- `exceptions` — all `ExceptionRecord`s from the run.
- `status_events` — full `StatusManager` event history.
- `succeeded` — `True` if no knot produced `Err`.
- `run_id` — UUID of this run.

**See also:** [API — Core](../api/core.md)

---

## KnotConfig

The per-knot configuration object. Passed as `_config=KnotConfig(...)`. Fields:

| Field | Default | Description |
|-------|---------|-------------|
| `id` | required | Unique knot id within the tapestry |
| `error_policy` | `SKIP_IF_PARENT_FAILED` | How to handle parent failures |
| `validate_io` | `True` | Whether to validate inputs/outputs with Pydantic |
| `description` | `""` | Human-readable description (visible in viz) |
| `tags` | `[]` | Arbitrary string tags |

---

## ErrorPolicy

A per-knot enum controlling how parent failures propagate:

| Policy | Behaviour |
|--------|-----------|
| `SKIP_IF_PARENT_FAILED` | Any parent `Err` or `Skipped` → this knot becomes `Skipped` (default). |
| `RECEIVE_ERRORS` | `process()` is called with `Result` objects directly. You handle errors. |
| `REQUIRE_ALL_PARENTS` | Any parent `Err` or `Skipped` → this knot produces a synthetic `Err`. |

**See also:** [Error Handling](../guides/error-handling.md)

---

## Content-addressed hashing

Every value that flows through a pipeline is identified by `sha256:<hex-digest>` computed from a canonical JSON serialisation. The same value always produces the same hash regardless of which run or which machine produced it (for standard Python types). This is the foundation of pirn's cross-run lineage queries.

The `DataStore` keys values by their hash. The `RunHistory` stores hashes in lineage records. You can scrub values (for GDPR etc.) from the `DataStore` without breaking the lineage graph.

**See also:** [Architecture — Content-Addressed Lineage](../architecture/overview.md#content-addressed-lineage)

---

## TapestryStore

The backend that stores the tapestry *definition* — the registered knots. Three protocols are implemented: `register`, `get`, `all`, `snapshot`.

**See also:** [Backends](../guides/backends.md), [API — Backends](../api/backends.md)

---

## RunHistory

The backend that stores run results and lineage records. Key queries: `record_run`, `get_run`, `query_lineage_by_output_hash`, `query_lineage_by_input_hash`, `query_lineage_by_knot_id`.

**See also:** [Backends](../guides/backends.md), [API — Backends](../api/backends.md)

---

## DataStore

The backend that stores intermediate values keyed by content hash. Decoupled from `RunHistory` so values can be scrubbed independently of the lineage audit trail.

**See also:** [Backends](../guides/backends.md), [API — Backends](../api/backends.md)
