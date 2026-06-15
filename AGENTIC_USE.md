# AGENTIC_USE — pirn 0.3.0

> pirn is an async, typed pipeline framework that composes work as a DAG of *knots*, runs them with content-addressed lineage, and produces structured three-way results (Ok / Err / Skipped) — it does NOT execute work itself, supply data, or manage infrastructure.

---

## Mental model

A **Tapestry** is the container for a pipeline. You declare it as a Python context manager (`with Tapestry() as t:`). Every knot constructed inside that block self-registers with the active tapestry via a context variable — no explicit `add()` call is needed. When the `with` block exits, the tapestry is sealed and ready to run. The pipeline definition lives in the tapestry; you run it by calling `await t.run(RunRequest(...))`.

A **Knot** is the unit of work. It has exactly one method you implement: `async def process(self, ..., **_: Any)`. The constructor — not the method — is where you wire the graph: pass another knot as a keyword argument and pirn treats it as a parent dependency; pass any other value and pirn treats it as a config constant. There is no separate `parents=` dict. The reserved kwarg `_config=KnotConfig(id="my-id")` carries framework metadata and is required on every knot. Knots are frozen (immutable) after `__init__` completes.

A **Parameter** is the canonical entry point for data that varies between runs. It is also a knot (no parents, no process logic to implement) and its value is bound from `RunRequest(parameters={"name": value})` at run time. The engine resolves the full graph in topological waves, caches intermediate values by content hash, and stores a `KnotLineage` record per knot per run. Each result is one of `Ok(value)`, `Err(record)`, or `Skipped(reason)` — never a bare exception. By default, if a parent produces `Err` or `Skipped`, downstream knots are skipped rather than crashed.

---

## Source map

```
pirn/
├── __init__.py              ← fills the sweet_tea registry at import time; built-in knots become addressable by name in YAML
├── core/
│   ├── knot.py              ← Knot base class: constructor wiring, freeze guard, fan-out logic, __call__ framework entry point
│   ├── knot_config.py       ← KnotConfig Pydantic model: id (required), error_policy, validate_io, description, tags
│   ├── knot_factory.py      ← @knot decorator and KnotFactory: promotes a plain async/sync function into a Knot subclass factory
│   ├── parameter.py         ← Parameter knot: no parents, value supplied via RunRequest or default at run time
│   ├── run_request.py       ← RunRequest: carries parameters dict and optional run_id for a single execution
│   ├── run_result.py        ← RunResult: outputs dict, lineage list, succeeded bool, exceptions list
│   ├── error_policy.py      ← ErrorPolicy enum: SKIP_IF_PARENT_FAILED, RECEIVE_ERRORS, REQUIRE_ALL_PARENTS
│   ├── ok.py                ← Ok result wrapper
│   ├── err.py               ← Err result wrapper
│   ├── skipped.py           ← Skipped result wrapper
│   ├── optional.py          ← Optional mixin: makes Err from this knot propagate as Skipped to downstream
│   ├── result.py            ← Result union type (Ok | Err | Skipped)
│   ├── assembler.py         ← Assembler marker base: thin Knot subclass identifying raw→Payload boundary knots
│   └── disassembler.py      ← Disassembler marker base: thin Knot subclass identifying Payload→raw boundary knots
├── nodes/
│   ├── source.py            ← Source base: zero-parent knot; subclass and implement process() with no named params
│   ├── sink.py              ← Sink base: terminal consumer; output is conventionally None; taxonomic, not enforced
│   ├── sub_tapestry.py      ← SubTapestry base: knot whose body is a complete inner tapestry; implement process() returning the terminal Knot
│   ├── gate/gate.py         ← Gate: one parent + predicate callable → Ok(value) if truthy, Skipped if falsy
│   ├── aggregator.py        ← Aggregator: N parents merged via a combine callable
│   ├── branch/branch.py     ← Branch: one parent + selector → tagged paths; non-selected paths are Skipped
│   ├── map_markers.py       ← Map / ZipMap / DictMap marker wrappers for fan-out construction
│   ├── reduce_.py           ← Reduce node: folds a list parent to one value (whole-list or pairwise)
│   ├── continuation.py      ← WithContinuation / continues(): deterministic successor attachment post-run
│   └── loop_sub_tapestry.py ← LoopSubTapestry: iterative SubTapestry with knots in one extensible run
├── tapestry.py              ← Tapestry class: context manager, register(), run(), terminals(), get_current_store()
├── domains/                 ← domain-specific knot libraries (data, agents, ml, health, signal, oilgas); deps via optional extras
├── backends/                ← pluggable storage backends (in_memory, sqlite, postgres, duckdb, valkey, s3, local_disk)
├── engine/                  ← internal execution engine and dispatchers (Local, Thread, Dask, Ray, Celery)
├── emitters/                ← run-event fan-out (Log, Kafka, OpenTelemetry, Webhook, ValKey)
├── triggers/                ← run-start triggers (Cron, Kafka, Webhook, ValKey)
├── streaming/               ← continuous-source adapters (IterableSource, FileTailSource, KafkaStreamingSource)
└── managers/                ← internal run-time helpers: exception records, knot state machine, status events, redaction
```

---

## Canonical pattern

Three equivalent ways to define a knot:

### A — `@knot` decorator (functions, quick prototyping)

```python
import asyncio
from typing import Any
from pirn import Tapestry, Parameter, KnotConfig, knot, RunRequest

# **_: Any is mandatory — absorbs implicit ordering dependencies.
@knot
async def clean(rows: list[dict], drop_nulls: bool, **_: Any) -> list[dict]:
    return [r for r in rows if all(r.values())] if drop_nulls else rows

@knot
async def summarise(rows: list[dict], **_: Any) -> dict:
    return {"count": len(rows)}

async def main():
    with Tapestry() as t:
        raw        = Parameter("raw",        list, _config=KnotConfig(id="raw"))
        drop_nulls = Parameter("drop_nulls", bool, default=True,
                               _config=KnotConfig(id="drop_nulls"))

        cleaned = clean(rows=raw, drop_nulls=drop_nulls, _config=KnotConfig(id="clean"))
        summarise(rows=cleaned, _config=KnotConfig(id="summarise"))

    result = await t.run(RunRequest(parameters={"raw": [{"id": 1}, {"id": None}]}))
    print(result.outputs["summarise"])  # {"count": 1}

asyncio.run(main())
```

### B — `Knot` subclass (production code, complex logic, dependencies injected via constructor)

```python
import asyncio
from typing import Any
from pirn import Knot, Tapestry, Parameter, KnotConfig, RunRequest

class Normalise(Knot):
    """Lower-case and strip whitespace from every string field."""

    def __init__(self, *, rows: Any, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(rows=rows, _config=_config, **kwargs)

    async def process(self, rows: list[dict], **_: Any) -> list[dict]:
        return [{k: v.strip().lower() if isinstance(v, str) else v
                 for k, v in row.items()} for row in rows]

async def main():
    with Tapestry() as t:
        raw      = Parameter("raw", list, _config=KnotConfig(id="raw"))
        Normalise(rows=raw, _config=KnotConfig(id="normalise"))

    result = await t.run(RunRequest(parameters={"raw": [{"name": "  Alice  "}]}))
    print(result.outputs["normalise"])  # [{"name": "alice"}]

asyncio.run(main())
```

### C — YAML pipeline (declarative, config-driven, no Python wiring code)

```yaml
# pipeline.yaml
name: etl
allow_callable_refs: true
allowed_module_prefixes:
  - myapp.knots          # only these modules may be referenced

nodes:
  - id: raw
    type: parameter
    type_: list

  - id: normalise
    type: knot
    callable: myapp.knots.normalise   # must be a @knot function or Knot subclass
    parents:
      rows: raw                       # kwarg name: source node id

  - id: summarise
    type: knot
    callable: myapp.knots.summarise
    parents:
      rows: normalise
```

```python
import asyncio
from pirn import load_pipeline, RunRequest
import pathlib

async def main():
    t = load_pipeline(pathlib.Path("pipeline.yaml").read_text(),
                      known_callables={})   # known_callables overrides callable refs
    result = await t.run(RunRequest(parameters={"raw": [{"name": "  Alice  "}]}))
    print(result.outputs["summarise"])

asyncio.run(main())
```

> **YAML security note:** `allow_callable_refs: true` executes arbitrary Python imports.
> Always set `allowed_module_prefixes` and never load user-supplied YAML with this flag.

---

## Extension points

### Knot

**Contract:** subclass `Knot`, implement `async def process(self, ..., **_: Any) -> T`. Every named parameter on `process` must be supplied as a kwarg at construction time. `**_: Any` is required — it absorbs implicit ordering dependencies and is enforced by `__init_subclass__`.

**Must not:** declare `*args` on `process` (raises `TypeError` at class definition time). Mutate instance attributes after `__init__` completes — knots are frozen and `__setattr__` will raise.

```python
from typing import Any
from pirn import Knot, KnotConfig

class Normalise(Knot):
    async def process(self, value: float, scale: float, **_: Any) -> float:
        return value / scale

with Tapestry() as t:
    raw    = ...  # some upstream knot
    normed = Normalise(value=raw, scale=100.0, _config=KnotConfig(id="norm"))
    #                              ^^^^^^^^^^^ scalar → config constant
```

### Source

**Contract:** subclass `Source`, implement `async def process(self, **_: Any) -> T` with no named parameters. Sources may not accept any kwarg other than `_config` and `tapestry`.

```python
from pirn import Source, KnotConfig
import json, pathlib

class ReadConfig(Source):
    async def process(self, **_: Any) -> dict:
        return json.loads(pathlib.Path("config.json").read_text())

with Tapestry() as t:
    cfg = ReadConfig(_config=KnotConfig(id="config"))
```

### Sink

**Contract:** subclass `Sink`, implement `async def process(self, ..., **_: Any) -> None`. Wire it to upstream knots the same way as any knot; return value is conventionally `None` but not enforced.

```python
from pirn import Sink, KnotConfig
import json

class WriteOutput(Sink):
    async def process(self, data: list[dict], path: str, **_: Any) -> None:
        pathlib.Path(path).write_text(json.dumps(data))

with Tapestry() as t:
    rows = ...  # upstream knot
    WriteOutput(data=rows, path="/tmp/out.json", _config=KnotConfig(id="write"))
```

### Assembler

**Contract:** subclass `Assembler` (from `pirn.core.assembler`), implement `async def process(self, ..., **_: Any) -> Payload`. Receives raw connector output (bytes, list[tuple], list[dict]) and converts it to a domain `Payload` subclass. Must not perform I/O — values arrive already materialised from a connector parent knot.

```python
from typing import Any
from pirn.core.assembler import Assembler
from pirn.core.knot_config import KnotConfig

class SignalObjectStoreAssembler(Assembler):
    async def process(self, body: bytes, signal_id: str, **_: Any) -> SignalPayload:
        if not isinstance(body, bytes) or not body:
            raise TypeError("body must be non-empty bytes")
        # decode bytes → SignalPayload via domain library
        return _decode(body, signal_id)
```

Lives in `pirn/domains/{domain}/assemblers/`. Named `{Subject}{Source}Assembler`.

### Disassembler

**Contract:** subclass `Disassembler` (from `pirn.core.disassembler`), implement `async def process(self, ..., **_: Any) -> bytes | list[tuple] | ...`. Receives a domain `Payload` subclass and converts it to raw types for a connector sink. Must not perform I/O.

```python
from typing import Any
from pirn.core.disassembler import Disassembler

class SignalObjectStoreDisassembler(Disassembler):
    async def process(self, payload: SignalPayload, **_: Any) -> bytes:
        if not isinstance(payload, SignalPayload):
            raise TypeError("payload must be SignalPayload")
        return _encode(payload)
```

Lives in `pirn/domains/{domain}/disassemblers/`. Named `{Subject}{Sink}Disassembler`.

### SubTapestry

**Contract:** subclass `SubTapestry`, implement `async def process(self, ..., **_: Any) -> Knot`. Inside `process`, build the inner graph by constructing knots (they auto-register in the framework-managed inner tapestry) and return the terminal `Knot`. The base class owns the `Tapestry()` context — do not open one yourself, and do not call `_run_inner` directly. Outer parent values arrive as resolved Python values in `**kwargs`. If the inner run has any exceptions, the base class converts them to `Err`.

```python
from typing import Any
from pirn import KnotConfig, Parameter
from pirn.nodes.sub_tapestry import SubTapestry

class ProcessBatch(SubTapestry):
    """Inner tapestry: validate and store must both succeed."""

    async def process(self, batch: list[dict], **_: Any) -> Knot:
        p = Parameter("batch", list, default=batch, _config=KnotConfig(id="batch"))
        ValidateRows(rows=p, _config=KnotConfig(id="validate"))
        return StoreRows(rows=p, _config=KnotConfig(id="store"))
```

### LoopSubTapestry

**Contract:** subclass `LoopSubTapestry[S]`, implement `step(state: S) -> tuple[Tapestry, S] | None` and `fold(state: S, result: RunResult) -> S`. The base class drives the iteration loop as a single extensible inner run — each iteration is a real, traceable knot. Do not override `process()`.

- `step` — given current state, return `(tapestry, updated_state)` to continue, or `None` to terminate.
- `fold` — integrate the completed iteration's `RunResult` into state; return new state for the next `step`.
- `step_id(state, idx)` — optional override; returns the knot ID for iteration `idx` (1-based). Default: `step_{idx}`.

```python
from typing import Any
from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.tapestry import Tapestry

class RefineLoop(LoopSubTapestry[float]):
    def __init__(self, *, max_rounds: int = 10, **kwargs: Any) -> None:
        self._max_rounds = max_rounds
        super().__init__(**kwargs)

    def step(self, state: float) -> tuple[Tapestry, float] | None:
        if state >= 1.0 or self._max_rounds <= 0:
            return None
        with Tapestry() as t:
            RefineKnot(value=state, _config=KnotConfig(id="refine"))
        return t, state

    def fold(self, state: float, result: RunResult) -> float:
        return result.outputs["refine"]

    def step_id(self, state: float, idx: int) -> str:
        return f"round_{idx}"
```

Wire like any other knot — `state` is the initial loop state:

```python
with Tapestry() as t:
    RefineLoop(state=0.1, max_rounds=5, _config=KnotConfig(id="loop"))

result = await t.run(RunRequest())
final_value = result.outputs["loop"]   # final state after all iterations
```

See [docs/guides/agentic-loops.md](docs/guides/agentic-loops.md) for the full contract, observability details, and a conversational LLM agent example.

---

### Parameter

**When to use:** any value that varies between runs. Construct it inside the `Tapestry` context and pass it as a kwarg to downstream knots exactly like any other knot. Values are bound at run time from `RunRequest(parameters={"name": value})`.

**Special constructor:** `Parameter(name, type_, *, default=..., _config=KnotConfig(id=...))`. `_config` is optional for `Parameter` — if omitted, the id defaults to `"param:{name}"`. Do not pass process-signature kwargs to a Parameter; it has none.

```python
with Tapestry() as t:
    # With default — knot still runs even if not supplied in RunRequest.
    threshold = Parameter("threshold", float, default=0.5,
                          _config=KnotConfig(id="threshold"))
    # Without default — RunRequest must supply "date" or the run raises.
    run_date  = Parameter("date", str, _config=KnotConfig(id="date"))
```

---

## Anti-patterns

### Passing a scalar where a Knot is expected and the param is typed `Knot | T`

**Looks right because:** the scalar is the "real" value and feels natural to pass directly.
**Wrong because:** scalars passed for `Knot | T` params are auto-coerced into anonymous `Parameter` nodes with auto-generated ids (`auto:{knot_id}:{param}`). These show up in lineage records with generated names, which is confusing and unintended. The auto-coercion exists as a convenience for quick prototyping, not as a production pattern.
**Do instead:** wrap the constant in an explicit `Parameter` with a stable id, or type the param as just `T` and let pirn treat it as a config constant (no auto-coercion, not in lineage).

### Constructing a knot outside a Tapestry context without passing `tapestry=`

**Looks right because:** the knot object is created and holds its wiring.
**Wrong because:** the knot is never registered with any tapestry, so `t.run()` will not execute it and it will not appear in lineage. No error is raised at construction — the failure is silent.
**Do instead:** always construct knots either inside `with Tapestry() as t:` or pass `tapestry=t` explicitly.

### Naming a `process()` parameter `_config` or `tapestry`

**Looks right because:** they are valid Python identifiers.
**Wrong because:** both names are in `Knot._reserved_kwargs`. `_declared_input_names` raises `TypeError` at construction the first time any instance is created, with the message "conflicts with a framework-reserved kwarg".
**Do instead:** use any other name (e.g. `config_data`, `tapestry_ref`).

### Skipping `_config=KnotConfig(id=...)`

**Looks right because:** the id feels like plumbing, not logic.
**Wrong because:** `Knot.__init__` raises `TypeError` immediately — "requires `_config=KnotConfig(id=...)`. Pirn requires explicit knot ids; nothing is auto-generated."
**Do instead:** always pass `_config=KnotConfig(id="your-stable-id")`. The id appears in lineage records, visualisations, and `result.outputs` keys, so choose something meaningful.

### Declaring `*args` on `process()`

**Looks right because:** `*args` is common Python.
**Wrong because:** `__init_subclass__` scans the `process` signature at class-definition time and raises `TypeError` ("may not declare *args") before any instance is ever created.
**Do instead:** use only named keyword arguments plus `**_: Any`.

### Mutating instance state after construction

**Looks right because:** Python usually allows attribute assignment on instances.
**Wrong because:** knots are frozen after `__init__` completes. Any attribute set whose name does not start with `_mutable_` raises `AttributeError` from `__setattr__`.
**Do instead:** compute all state inside `__init__` before calling `super().__init__()`, or store mutable state externally (e.g. pass a mutable container in as config).

### Passing `validate_io=False` everywhere to silence type errors

**Looks right because:** it makes construction-time errors go away.
**Wrong because:** `KnotConfig(validate_io=False)` disables Pydantic validation for both inputs and outputs, removing one of pirn's main safety nets. Type mismatches become silent data corruption at runtime.
**Do instead:** fix the type annotations or coerce values upstream. Only use `validate_io=False` when working with types pydantic cannot schema (e.g. `RunResult` from SubTapestry, as seen in the examples).

---

## Constraints and gotchas

- **Knot ids must match `[a-zA-Z0-9_\-\.:]{1,256}`**: any other character raises `ValueError` in `KnotConfig` validation. Spaces, slashes, and null bytes are not allowed.
- **`result.outputs` keys are knot ids**: access outputs as `result.outputs["my-id"]`. Missing keys mean the knot was skipped or errored — check `result.succeeded` first.
- **Default error policy skips downstream on failure**: if a parent knot produces `Err` or `Skipped`, all children are `Skipped` by default. To receive the error in `process()`, set `error_policy=ErrorPolicy.RECEIVE_ERRORS` in `KnotConfig` — your method then receives `Result` objects rather than bare values.
- **`tapestry.run()` is a coroutine**: always `await` it. Calling without `await` returns a coroutine object and nothing executes.
- **`SubTapestry._run_inner` raises on any inner exception**: the outer pipeline sees `Err`, not the inner `RunResult`. The `RunResult` is attached to the `SubTapestryError` for inspection if needed.
- **Mid-run extension requires `InMemoryStore`**: `tapestry.run(extensible=True)` and `get_current_store()` only work with the default in-memory backend. SQLite, Postgres, and ValKey stores do not yet support it.
- **Pickle is used by S3, ValKey, and LocalDisk data stores**: these backends serialize intermediate values with pickle. Only use them when the backing store is not writable by adversaries.
- **`WebhookTrigger` has no built-in authentication**: always place an authenticating proxy in front of it before exposing to any network.
- **Streaming sources via `run_stream`, not `run`**: continuous data pipelines use `pirn.streaming.run_stream(source, tapestry)`, not `tapestry.run()`.
- **YAML `allow_callable_refs: true` executes arbitrary imports**: only use with YAML from trusted authors, never user-supplied YAML.
- **`Optional` is a mixin, not a flag**: to make a knot's `Err` propagate as `Skipped`, declare `class MyKnot(Optional, Knot):` — do not try to pass it as an argument.

---

## Worked examples

### Example 1 — Simple linear ETL pipeline

```python
import asyncio
from pirn import Tapestry, Parameter, KnotConfig, knot, RunRequest

@knot
async def extract(source_csv: str, **_) -> list[dict]:
    import csv, io
    return list(csv.DictReader(io.StringIO(source_csv)))

@knot
async def clean(rows: list[dict], drop_empty: bool, **_) -> list[dict]:
    if not drop_empty:
        return rows
    return [r for r in rows if all(v.strip() for v in r.values())]

@knot
async def summarise(rows: list[dict], **_) -> dict:
    return {"count": len(rows), "ids": [r.get("id") for r in rows]}

async def main():
    with Tapestry() as t:
        csv_text   = Parameter("csv_text",   str,  _config=KnotConfig(id="csv_text"))
        drop_empty = Parameter("drop_empty", bool, default=True,
                               _config=KnotConfig(id="drop_empty"))

        raw     = extract(source_csv=csv_text, _config=KnotConfig(id="extract"))
        cleaned = clean(rows=raw, drop_empty=drop_empty, _config=KnotConfig(id="clean"))
        summarise(rows=cleaned, _config=KnotConfig(id="summarise"))

    result = await t.run(RunRequest(parameters={
        "csv_text": "id,name\n1,alice\n2,\n3,carol",
    }))

    assert result.succeeded
    print(result.outputs["summarise"])  # {"count": 2, "ids": ["1", "3"]}
    for rec in result.lineage:
        print(f"  {rec.knot_id:<12} {rec.outcome}")

asyncio.run(main())
```

### Example 2 — SubTapestry composition

```python
import asyncio
from dataclasses import dataclass
from typing import Any

from pirn import Tapestry, Parameter, KnotConfig, knot, RunRequest
from pirn.core.run_result import RunResult
from pirn.nodes.sub_tapestry import SubTapestry

@dataclass
class Order:
    order_id: str
    items: list[str]
    total: float

@knot
async def check_inventory(order: Order, **_) -> list[str]:
    catalog = {"widget", "gadget"}
    missing = [i for i in order.items if i not in catalog]
    if missing:
        raise ValueError(f"unknown items: {missing}")
    return order.items

@knot
async def charge(order: Order, **_) -> str:
    if order.total >= 10_000:
        raise ValueError("payment declined")
    return f"AUTH-{order.order_id}"

class ValidateOrder(SubTapestry):
    """Inner tapestry: inventory + payment must both succeed."""
    async def process(self, order: Order, **_: Any) -> RunResult:
        with Tapestry() as inner:
            p = Parameter("order", Order, default=order, _config=KnotConfig(id="order"))
            check_inventory(order=p, _config=KnotConfig(id="inventory"))
            charge(order=p,          _config=KnotConfig(id="charge"))
        return await self._run_inner(inner)

@knot
async def notify(order: Order, validation: RunResult, **_) -> str:
    auth = validation.outputs["charge"]
    return f"Order {order.order_id} confirmed. Auth: {auth}"

async def main():
    with Tapestry() as t:
        order_param = Parameter("order", Order, _config=KnotConfig(id="order"))

        validated = ValidateOrder(
            order=order_param,
            _config=KnotConfig(id="validate", validate_io=False),
        )
        notify(
            order=order_param,
            validation=validated,
            _config=KnotConfig(id="notify", validate_io=False),
        )

    good_order = Order("ORD-1", ["widget", "gadget"], 99.0)
    result = await t.run(RunRequest(parameters={"order": good_order}))
    assert result.succeeded
    print(result.outputs["notify"])  # "Order ORD-1 confirmed. Auth: AUTH-ORD-1"

    bad_order = Order("ORD-2", ["widget", "unobtainium"], 50.0)
    result2 = await t.run(RunRequest(parameters={"order": bad_order}))
    assert not result2.succeeded
    print(result2.exceptions[0].message)  # "unknown items: ['unobtainium']"

asyncio.run(main())
```

---

## Quick reference

| Task | How |
|------|-----|
| Define a knot (decorator) | `@knot` on an `async def f(x: T, **_: Any) -> R` |
| Define a knot (class) | `class MyKnot(Knot): async def process(self, x: T, **_: Any) -> R` |
| Wire two knots | pass upstream knot as kwarg: `B(input=a_knot, _config=KnotConfig(id="b"))` |
| Inject a constant (config) | pass scalar for a non-`Knot|T` param — stays invisible in lineage |
| Inject a run-time variable | `Parameter("name", type_, _config=KnotConfig(id="p"))`, supply via `RunRequest` |
| Run a pipeline | `await tapestry.run(RunRequest(parameters={"name": value}))` |
| Read an output | `result.outputs["knot-id"]` — `KeyError` means knot was skipped or errored |
| Check success | `result.succeeded` (False if any knot produced Err) |
| Handle upstream errors | `KnotConfig(error_policy=ErrorPolicy.RECEIVE_ERRORS)` — `process()` receives `Result` |
| Skip on predicate | `Gate(input=knot, predicate=fn, _config=KnotConfig(id="g"))` |
| Fan over a list | `Map(over=list_knot, each=per_item_factory, bind="item", _config=...)` |
| Compose sub-pipelines | subclass `SubTapestry`; build inner graph in `process()`; return terminal `Knot` |
| Iterative / agentic loop | subclass `LoopSubTapestry[S]`; implement `step()` and `fold()`; wire `state=initial` |
| Custom step IDs in history | override `step_id(state, idx) -> str` on `LoopSubTapestry` subclass |
| Make Err propagate as Skipped | `class MyKnot(Optional, Knot):` |
| Add observability | `Tapestry(emitters=[LogEmitter(), OpenTelemetryEmitter()])` |
| Scale to threads | `Tapestry(dispatcher=ThreadDispatcher(max_workers=8))` |
| Persist lineage | `Tapestry(history=SQLiteHistory(path="pirn.db"))` |
| Visualise a run | `from pirn import html_for_run; Path("run.html").write_text(html_for_run(result))` |
| Load pipeline from YAML | `from pirn import load_pipeline; t = load_pipeline(yaml_text, known_callables={...})` |

---

## Domain guides

Each domain has its own `AGENTIC_USE.md` covering domain-specific mental models,
source maps, interfaces, anti-patterns, and quick references. Read the relevant
domain guide alongside this file before writing domain code.

| Domain | Guide | Install extra |
|--------|-------|---------------|
| Agents — LLM pipelines, tool use, RAG, ReAct, multi-agent | [packages/pirn-agents/src/pirn_agents/AGENTIC_USE.md](packages/pirn-agents/src/pirn_agents/AGENTIC_USE.md) | `pirn-agents` |
| Data — tiered dataframe transforms (Polars, DuckDB, Ibis, …) | [pirn/domains/data/AGENTIC_USE.md](pirn/domains/data/AGENTIC_USE.md) | `pirn[data]` |
| ML — training, evaluation, deployment, artifact formats | [pirn/domains/ml/AGENTIC_USE.md](pirn/domains/ml/AGENTIC_USE.md) | `pirn[ml]` |
| Health — DICOM, FHIR, HL7v2, EDF, genomics, PHI redaction | [pirn/domains/health/AGENTIC_USE.md](pirn/domains/health/AGENTIC_USE.md) | `pirn[health]` |
| Signal — DSP, filters, spectral, wavelets, audio | [packages/pirn-signal/src/pirn_signal/AGENTIC_USE.md](packages/pirn-signal/src/pirn_signal/AGENTIC_USE.md) | `pirn-signal[signal]` |
| Oil & Gas — SEG-Y, LAS, WITSML, seismic, well, production | [pirn/domains/oilgas/AGENTIC_USE.md](pirn/domains/oilgas/AGENTIC_USE.md) | `pirn[oilgas]` |

---

*Generated for agent use. Covers pirn 0.x*
