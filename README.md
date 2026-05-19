<p align="center">
  <img src="docs/pirn_logo.png" alt="pirn" width="120">
</p>

<h1 align="center">pirn</h1>
<p align="center">A pipeline framework where everything is a knot.</p>

`pirn` builds typed, async, observable data and computation pipelines. You wire
work into a *tapestry* of *knots*, run it, and get back a structured result —
including content-addressed lineage records you can join across runs.

```bash
pip install pirn  # not yet on PyPI; this repo is the source
```

Requires Python 3.11+.

## Quickstart

```python
import asyncio
from pirn import Tapestry, Parameter, KnotConfig, knot, RunRequest

@knot
async def double(x: int) -> int:
    return x * 2

@knot
async def add(a: int, b: int) -> int:
    return a + b

async def main():
    with Tapestry() as t:
        x = Parameter("x", int)
        d = double(x=x, _config=KnotConfig(id="d"))
        answer = add(a=x, b=d, _config=KnotConfig(id="answer"))

    result = await t.run(RunRequest(parameters={"x": 5}))
    print(result.outputs)  # {'param:x': 5, 'd': 10, 'answer': 15}

asyncio.run(main())
```

That's the whole shape: declare knots inside a `Tapestry()` context, wire them
by passing one knot as a kwarg of another, run.

## The constructor convention

When you construct a knot, pirn looks at every kwarg:

* If the value **is itself a knot**, it becomes a **parent** — this knot
  depends on the other knot's output.
* Otherwise, the value is **config** — a constant fed in at run time.

So `add(a=x, b=d, _config=KnotConfig(id="answer"))` makes `x` and `d` parents
of `answer`. There's no separate `parents={...}` dict to remember.

Framework metadata (the knot's id, error-handling policy, validation toggle)
goes in the reserved `_config=` kwarg, which keeps the framework's namespace
out of yours.

Every knot needs an explicit id — pirn doesn't auto-generate them, because
auto-generated ids make lineage records unreadable.

## Tapestry

A `Tapestry` is the workspace your knots live in. Constructing knots inside
`with Tapestry() as t:` auto-registers them. You can also pass `tapestry=`
explicitly, or hand a knot directly to `t.register(knot)`.

`t.run(request)` walks from the tapestry's terminal knots (those with no
downstream consumers) and runs the whole graph reachable from them. To run a
specific subset, pass `terminals=knot_or_list`.

A tapestry holds three backends:

| Backend         | What it stores                                  | Defaults / Phase 3 options                  |
|-----------------|-------------------------------------------------|---------------------------------------------|
| `TapestryStore` | the canonical knot definitions                  | `InMemoryStore`, `SQLiteStore`, `PostgresStore`, `ValKeyStore` |
| `RunHistory`    | run results and lineage records                 | `InMemoryHistory`, `SQLiteHistory`, `DuckDBHistory`, `PostgresHistory` |
| `DataStore`     | intermediate values, keyed by content hash      | `InMemoryDataStore`, `LocalDiskDataStore`, `ValKeyDataStore`, `S3DataStore` |

They're separate so each can be picked for its strength: Postgres for both
store and history when you want one durable database; SQLite store +
DuckDB history when you want OLAP-fast lineage queries; ValKey for the
data store where content-addressed values fit a key-value store
naturally; S3 when intermediate values are large or shared across many
workers.

Each backend lives behind an extra: `pip install pirn[sqlite]`,
`pirn[postgres]`, `pirn[valkey]`, `pirn[duckdb]`, `pirn[s3]`, or
`pirn[all]` for everything.

## Result is three-way

Every knot produces an `Ok`, an `Err`, or a `Skipped`:

* `Ok(value)` — success.
* `Err(record)` — failure; the record is a Pydantic `ExceptionRecord` with the
  type, message, traceback, and a stable id.
* `Skipped(reason)` — opted out, branch not selected, gate closed, parent
  failed under the default policy. Distinct from `Err` so downstream knots
  can react differently to "didn't run" vs "crashed".

By default, a knot whose parent produced `Err` or `Skipped` is itself
skipped (`SKIP_IF_PARENT_FAILED`). Other policies:

* `RECEIVE_ERRORS` — your `process()` is called with `Result` objects directly,
  so you handle errors yourself.
* `REQUIRE_ALL_PARENTS` — any failed/skipped parent makes this knot fail too.

Set per-knot via `_config=KnotConfig(id="...", error_policy=...)`.

## Optional knots

If you want an `Err` from a particular knot to behave like a `Skipped`
downstream, mix in `Optional`:

```python
from pirn import Optional, Knot

class FetchPrefs(Optional, Knot):
    async def process(self, user_id: str) -> dict:
        ...
```

`Optional` is a mixin, not a flag, so it composes cleanly with subclasses
that have their own behaviour.

## Lineage, content-addressed

Every knot execution produces a `KnotLineage` record:

```python
KnotLineage(
    run_id="run-abc",
    knot_id="answer",
    knot_class="my_pkg.knots.Add",
    knot_config_hash="sha256:…",       # the knot's config at run time
    parent_input_hashes={               # what it consumed
        "a": "sha256:…",
        "b": "sha256:…",
    },
    output_hash="sha256:…",            # what it produced
    outcome="ok",
    dispatcher="LocalDispatcher",
    started_at=…, finished_at=…,
)
```

Because hashes are content-addressed (sha256 of a stable canonicalisation),
the same value always hashes to the same string regardless of which run
produced it. This makes cross-run lineage queries trivial:

```python
# Did anything else in any past run produce this same output?
matches = await tapestry.history.query_lineage_by_output_hash(out_hash)

# Who else consumed this value as input?
consumers = await tapestry.history.query_lineage_by_input_hash(in_hash)

# What's this knot's run history?
records = await tapestry.history.query_lineage_by_knot_id("answer")
```

Lineage records reference values by hash; the `DataStore` holds the values.
You can scrub values from the data store (TTL, GDPR, whatever) without
losing the lineage graph.

## The node taxonomy

Beyond `Knot`, pirn ships a handful of specialised classes:

| Class              | Shape                                                              |
|--------------------|--------------------------------------------------------------------|
| `Source`           | zero parents → produces a value (file, DB query, fetch, …)         |
| `Sink`             | terminal consumer; output conventionally `None`                    |
| `Aggregator`       | N parents combined via a `combine` callable                        |
| `Branch`           | one input + selector → tagged path; non-selected paths are skipped |
| `Gate`             | one input + predicate → pass through or skip                       |
| `Map`              | fan a knot over every element of a parent's list                   |
| `ZipMap`           | fan a knot over multiple collections element-wise                  |
| `DictMap`          | fan a knot over the entries of a dict                              |
| `Reduce`           | folds a list parent into one value (whole-list or pairwise)        |
| `SubTapestry`      | a knot whose execution body is a complete inner tapestry           |
| `WithContinuation` | wraps a knot; spawns successors based on its output at runtime     |
| `LoopSubTapestry`  | iterative SubTapestry; iterations are knots in one extensible run  |

`Optional` is a mixin (not a node).

```python
from pirn import Map, Reduce, Aggregator, Gate, Branch

# Map an inner knot over a collection-producing parent.
users = Map(
    over=record_ids,
    each=enrich_record,
    bind="record_id",
    _config=KnotConfig(id="users"),
)

# Reduce a list to one value.
total = Reduce(of=users, combine=sum, _config=KnotConfig(id="total"))

# Branch on a selector.
b = Branch(
    input=msg,
    selector=lambda m: m["type"],
    branches=("tool", "response"),
    _config=KnotConfig(id="route"),
)
handle_tool(payload=b["tool"], _config=KnotConfig(id="t"))
handle_resp(payload=b["response"], _config=KnotConfig(id="r"))
```

## Dispatchers

The dispatcher decides where work runs.

* `LocalDispatcher` — runs in the current event loop. The default.
* `ThreadDispatcher(max_workers=...)` — offloads each knot to a global
  thread pool, useful for CPU-bound or sync-heavy work.
* `DaskDispatcher` — runs each knot on a Dask cluster
  (`pip install pirn[dask]`).
* `RayDispatcher` — runs each knot as a Ray task
  (`pip install pirn[ray]`).
* `CeleryDispatcher` — submits each knot through Celery
  (`pip install pirn[celery]`).

```python
from pirn import ThreadDispatcher
from pirn.engine.dask_dispatcher import DaskDispatcher

# In-process scaling.
with Tapestry(dispatcher=ThreadDispatcher(max_workers=8)) as t:
    ...

# Distributed scaling.
dispatcher = DaskDispatcher.local()  # or DaskDispatcher(scheduler="tcp://...")
with Tapestry(dispatcher=dispatcher) as t:
    ...
```

All dispatchers honor the same `Dispatcher` protocol; switching between
them doesn't change the rest of your pipeline.

## Triggers and emitters

A **trigger** starts a run when an external event arrives. An
**emitter** observes runs as they happen and fans events out to logs,
metrics, message buses, or traces.

### Triggers

```python
from pirn.triggers import CronTrigger, KafkaTrigger, WebhookTrigger, run_forever

# Run every five minutes.
trigger = CronTrigger(every_seconds=300)
await run_forever(trigger, tapestry)

# Run on each Kafka message.
trigger = KafkaTrigger(topic="orders", bootstrap_servers="kafka:9092")
await run_forever(trigger, tapestry)

# Run on each HTTP POST.  trigger.app is a Starlette ASGI app you mount on
# any ASGI server (uvicorn, hypercorn, FastAPI).
trigger = WebhookTrigger(path="/run")
import uvicorn
uvicorn.run(trigger.app, host="0.0.0.0", port=8080)
```

`ValKeyTrigger` (pubsub) is also available; full list in
`pirn.triggers`.

### Emitters

```python
from pirn import LogEmitter, KafkaEmitter, OpenTelemetryEmitter

# Stream structured logs.
log_emitter = LogEmitter(with_payload=False)

# Publish to Kafka for downstream observability tools.
kafka_emitter = KafkaEmitter(
    bootstrap_servers="kafka:9092",
    topic_status="pirn.status",
    topic_lineage="pirn.lineage",
    topic_result="pirn.result",
)

# OpenTelemetry trace spans per knot.
otel_emitter = OpenTelemetryEmitter()

with Tapestry(emitters=[log_emitter, kafka_emitter, otel_emitter]) as t:
    ...
```

`WebhookEmitter` and `ValKeyEmitter` are also available. A broken
emitter never breaks a run — exceptions inside emitters are isolated.

## Streaming sources

Triggers fire whole runs (request/response). **Streaming sources**
feed continuous data into a single long-running pipeline — ETL-style.

```python
from pirn.streaming import IterableSource, FileTailSource, run_stream

# Tail a log file forever.
source = FileTailSource("/var/log/app.log", parameter_name="line")
await run_stream(source, tapestry, on_result=handle)

# Wrap any iterable.
source = IterableSource([1, 2, 3], parameter_name="x")
await run_stream(source, tapestry)
```

`KafkaStreamingSource` is available too. If you want to drive
trigger-based machinery from a stream, wrap with
`StreamingSourceTrigger`.

## Mid-run extension and dynamic DAGs

For dynamic pipelines where a knot decides what comes next based on its
own output, opt into **extensible** runs:

```python
result = await tapestry.run(extensible=True)
```

Inside any knot's `process()`, call `get_current_store()` to register
successor knots into the running tapestry. The engine picks them up
between waves:

```python
from pirn.tapestry import get_current_store

class PlannerKnot(Knot):
    async def process(self, ctx: Context, **_) -> Context:
        store = get_current_store()
        if store is not None:
            for action in plan_actions(ctx):
                store.register(ActionKnot(ctx=self, action=action,
                                          _config=KnotConfig(id=action.id)))
        return ctx
```

Successor knots wired to `self` receive the planner's output as a real
data edge — the lineage reflects the true parent/child relationship, not
a shared state blob.

For continuation-style logic (deterministic next-steps attached to an
existing knot without modifying it), use `continues()`:

```python
from pirn.nodes.continuation import Next, continues

def router(result) -> list[Next]:
    if result.score > 0.8:
        return [Next("publish", {"data": result.content})]
    return [Next("review", {"data": result.content})]

continues(score_knot, fn=router, pool={"publish": PublishKnot, "review": ReviewKnot})
```

Requires `InMemoryStore` (the default). `SQLiteStore` and other
persistent stores do not yet support mid-run extension.

## Visualization

```python
from pirn import mermaid_for_tapestry, mermaid_for_run, html_for_run

# Mermaid for embedding in docs.
print(mermaid_for_tapestry(t))           # structure only
print(mermaid_for_run(result))           # structure + outcome colors

# Standalone HTML/SVG for browsing.
Path("run.html").write_text(html_for_run(result))
```

The HTML renderer produces a single self-contained file with hover
tooltips (knot id, class, outcome, hashes, duration), filter buttons
by outcome, and a longest-path layout — no server, no external assets.

## YAML pipelines

Pipelines can be declared in YAML and loaded with `load_pipeline`.

```yaml
name: simple
nodes:
  - id: x
    type: parameter
    type_: int
    has_default: true
    default: 5
  - id: doubled
    type: knot
    callable: double
    parents:
      x: x
  - id: answer
    type: knot
    callable: add
    parents:
      a: x
      b: doubled
```

```python
from pirn import load_pipeline, RunRequest

t = load_pipeline(
    yaml_text,
    known_callables={"double": double, "add": add},
)
result = await t.run(RunRequest())
```

Strict by default: every callable, predicate, selector, combine, or `each`
reference must be in `known_callables`. Set `allow_callable_refs: true` at
the top level to opt into dotted-path imports (loose mode).

## Security

pirn uses **pickle** to serialize intermediate values in the `S3DataStore`, `ValKeyDataStore`, and `LocalDiskDataStore` backends. Pickle is an arbitrary-code-execution primitive: only use these backends when the backing store is not writable by adversaries.

The `WebhookTrigger`'s built-in authentication is opt-in via the `auth_token=` constructor parameter. For defence-in-depth, also place an authenticating reverse proxy or middleware in front of it before exposing it to any network. See [docs/webhook-trigger-auth.md](docs/webhook-trigger-auth.md) for details.

Setting `allow_callable_refs: true` in a YAML pipeline **enables dynamic Python imports** from YAML content. Only use this with YAML authored by trusted developers — never with user-supplied YAML.

To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Documentation

| Document | Contents |
|----------|----------|
| [docs/architecture.md](docs/architecture.md) | Full architecture and design reference: execution model, backend matrix, extension points, Mermaid diagrams |
| [docs/choosing-backends.md](docs/choosing-backends.md) | When to use each storage backend |
| [docs/deployment-sizing.md](docs/deployment-sizing.md) | Sizing guidance for different deployment scales |
| [docs/observability.md](docs/observability.md) | Emitters, OTel, Kafka, log structure |
| [docs/schema-migrations.md](docs/schema-migrations.md) | Database schema migration procedures |
| [docs/subscribable-stores.md](docs/subscribable-stores.md) | Mid-run extension and subscribable store protocol |
| [SECURITY.md](SECURITY.md) | Responsible disclosure policy |

## Domain libraries

pirn ships domain-specific knot libraries for common data engineering and ML workloads. All domain libraries live under `pirn/domains/` in the same package — dependencies are isolated via optional extras so you install only what your project uses.

| Domain | Description | Extra |
|--------|-------------|-------|
| Data | Tiered data-frame knots (pandas, Polars, Ibis, Spark, DuckDB), lakehouse adapters, tabular transforms | `pirn[data]` |
| Agents | LLM-backed knots, tool use, memory stores, planning, RAG, ReAct, multi-agent patterns | `pirn[agents]` |
| ML | Data prep, feature engineering, training, evaluation, deployment, feature stores | `pirn[ml]` |
| Health | DICOM, FHIR, HL7v2, EDF/BDF, NIfTI, FASTA/FASTQ, VCF — medical imaging, genomics, clinical data | `pirn[health]` |
| Signal | Time-series, DSP, audio (WAV/FLAC/MP3), EEG/BDF, wavelet transforms | `pirn[signal]` |
| Oil & Gas | SEG-Y seismic, LAS well-log, WITSML — subsurface data connectors | `pirn[oilgas]` |

### File format coverage

pirn ships approximately 98 file formats across 16 categories: universal tabular (CSV, Parquet, ORC, Avro, Feather), office documents (XLSX, ODS, DOCX, PPTX, PDF, RTF), scientific (HDF5, NetCDF, Zarr, MATLAB), image (PNG, JPEG, TIFF, WebP, HEIC), geospatial (GeoJSON, Shapefile, KML, GeoTIFF, GeoPackage), ML artifacts (ONNX, SafeTensors, Joblib, PyTorch, TF SavedModel, GGUF, TFLite), compression codecs (gzip, bzip2, zstd, snappy, lz4), archive formats (tar, zip), lakehouse table formats (Delta Lake, Apache Iceberg, Apache Hudi), healthcare (DICOM, FHIR, HL7v2, EDF/BDF, CDA, NIfTI), genomics (FASTA, FASTQ, VCF, BCF), markup (HTML, Markdown, ePub), and more. See [docs/connectors/index.md](docs/connectors/index.md) for the full format matrix.

### PHI safety

Healthcare formats (DICOM, FHIR, HL7v2, EDF/BDF, CDA) include built-in PHI redaction support. Sensitive fields — patient names, dates of birth, MRNs, and other HIPAA-defined identifiers — can be scrubbed or pseudonymised before records flow into downstream knots. Redaction is opt-in per format instance and is audited through pirn's standard content-addressed lineage so every scrub event is traceable.

### ML deserialization security

`JoblibFormat` and `PytorchFormat` use pickle internally. Both constructors refuse to proceed without either a `_Signer` instance (HMAC-SHA256 signs payloads before emission and verifies before deserialisation) or an explicit `allow_unsigned=True` acknowledgement (intended for single-tenant dev/test environments only). `SafetensorsFormat` is RCE-safe by design and requires no signer. See [docs/domains/ml.md](docs/domains/ml.md) for the full security property table.

## Philosophy

* **Declarative wiring, imperative bodies.** Wiring happens in `Tapestry`
  context blocks; bodies are normal Python `async` functions.
* **Three-way results from the start.** Skip is not failure; both deserve
  first-class handling.
* **Lineage by default, not as an add-on.** Every run produces structured,
  content-addressed records that join across runs.
* **Backends are protocols.** SQLite, Postgres, DuckDB, ValKey, S3, local
  disk — pick the shape that fits your deployment without API churn.
* **Optional deps stay optional.** Each backend, dispatcher, trigger, and
  emitter is gated behind a `[bracket]` extra; install only what you use.

## Status

Phase 3 (current). Public API stable: every protocol from Phase 2 still
works, and Phase 3 adds the networked backends, distributed dispatchers,
event-driven triggers and emitters, streaming sources, mid-run
extension, and visualization on top.

For testing real backends (Postgres, ValKey, Kafka, S3) end-to-end, see
[docs/guides/testing.md](docs/guides/testing.md).

Apache-2.0.
