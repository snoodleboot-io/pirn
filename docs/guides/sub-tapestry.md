# SubTapestry

**Audience:** engineers building pirn pipelines who need a knot that contains its own complete pipeline internally.

---

## Table of Contents

1. [What is a SubTapestry](#1-what-is-a-subtapestry)
2. [When to use one](#2-when-to-use-one)
3. [The contract](#3-the-contract)
4. [A complete example](#4-a-complete-example)
5. [The Assembler pattern](#5-the-assembler-pattern)
6. [Inputs and wiring](#6-inputs-and-wiring)
7. [Error handling](#7-error-handling)
8. [Observability](#8-observability)
9. [Common mistakes](#9-common-mistakes)

---

## 1. What is a SubTapestry

A `SubTapestry` is a `Knot` whose execution body is a complete inner pipeline. From the outer tapestry's perspective it is just a knot — one node in the graph, one output, one failure mode. Inside, it runs its own tapestry with its own set of knots, its own topological ordering, and its own concurrency.

```
Outer tapestry
│
├── KnotA
├── KnotB
└── DatasetLoader (SubTapestry)          ← looks like one node here
        │
        └── Inner tapestry (hidden)
                ├── Optional(FileSource)
                ├── Optional(LakehouseTableSource)
                ├── Optional(SqlSource)
                ├── Aggregator
                └── DatasetAssembler     ← sink; its output becomes DatasetLoader's output
```

The outer pipeline never sees the inner tapestry. It sees `DatasetLoader`'s output — whatever the sink knot produced.

---

## 2. When to use one

Use a `SubTapestry` when:

- **Fan-in with Optional sources.** Multiple sources that might or might not be configured. Each is wrapped in `Optional`; an `Aggregator` picks the live one. The outer pipeline should not need to know which source ran.
- **Encapsulation of a reusable sub-graph.** A sequence of steps that logically belongs together, is used in multiple outer tapestries, and has a clean single output.
- **Conditional internal structure.** The shape of the inner graph depends on resolved input values. `process()` receives resolved inputs as plain values and can use them to decide what to build.

Do not use a `SubTapestry` just to add another layer of nesting. If the logic fits in a single `process()` method, write a plain `Knot`.

---

## 3. The contract

Subclass `SubTapestry` and implement one method:

```python
async def process(self, **resolved_inputs: Any) -> Knot:
    ...
```

**Rules:**

1. Build any knots inside `process()`. They auto-register into the inner tapestry — you do not create a `Tapestry()` context yourself.
2. Return the **terminal (sink) knot** — the knot whose output should become this `SubTapestry`'s output. This must be a knot built inside this call; returning a stray knot from elsewhere raises `ValueError`.
3. Do not call `_run_inner`. The base class handles running the inner graph.
4. Do not index into `result.outputs`. The base class extracts the sink's output and returns it transparently.

The base `__call__` handles the full lifecycle:

```
__call__(parent_results)
    │
    ├── merge config + resolved parent values into kwargs
    ├── validate inputs (if validate_io=True)
    ├── open Tapestry() context
    │       └── call process(**kwargs)     ← your code runs here
    │               returns a Knot (the sink)
    ├── close context (inner graph is now declared)
    ├── validate: sink is a Knot
    ├── validate: sink is registered in the inner tapestry
    ├── _run_inner(inner tapestry)
    ├── extract result.outputs[sink.knot_id]
    └── return Ok(output)
```

---

## 4. A complete example

```python
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.optional import Optional
from pirn.core.skipped import Skipped
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry


class _RawAssembler(Knot):
    """Terminal step: converts the raw batch into the domain payload."""

    async def process(self, batch: DataBatch, label: str, **_: Any) -> MyPayload:
        return MyPayload(data=batch.rows, label=label)


class MultiSourceLoader(SubTapestry):
    """Load data from whichever of three sources is configured.

    Exactly one of (file_source, lake_source, sql_source) must be provided.
    The others may be None — Optional wraps each one so construction and
    runtime failures silently become Skipped.
    """

    def __init__(
        self,
        *,
        label: Knot | str,
        file_source: Knot | FileSource | None = None,
        lake_source: Knot | LakeSource | None = None,
        sql_source: Knot | SqlSource | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            label=label,
            file_source=file_source,
            lake_source=lake_source,
            sql_source=sql_source,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        label: str,
        file_source: FileSource | None = None,
        lake_source: LakeSource | None = None,
        sql_source: SqlSource | None = None,
        **_: Any,
    ) -> Knot:
        file_k  = Optional(RawFileKnot,  source=file_source,  _config=KnotConfig(id="src-file"))
        lake_k  = Optional(RawLakeKnot,  source=lake_source,  _config=KnotConfig(id="src-lake"))
        sql_k   = Optional(RawSqlKnot,   source=sql_source,   _config=KnotConfig(id="src-sql"))
        agg     = Aggregator(
            combine=self._pick_present,
            file=file_k, lake=lake_k, sql=sql_k,
            _config=KnotConfig(id="agg"),
        )
        return _RawAssembler(batch=agg, label=label, _config=KnotConfig(id="assembler"))

    @staticmethod
    def _pick_present(**results: Any) -> Any:
        for v in results.values():
            if not isinstance(v, Skipped):
                return v
        raise RuntimeError("MultiSourceLoader: no source produced data")
```

Usage in an outer tapestry is identical to any other knot:

```python
with Tapestry() as t:
    loader = MultiSourceLoader(
        label="training-set",
        file_source=my_file_source,
        _config=KnotConfig(id="loader"),
    )
    trainer = ModelTrainer(dataset=loader, _config=KnotConfig(id="trainer"))

result = await t.run(RunRequest())
```

---

## 5. The Assembler pattern

`process()` must return a `Knot` — not a value. This means any transformation of the raw output must be a knot inside the inner graph. The terminal knot is an **Assembler**: a plain `Knot` whose job is to convert the last intermediate value into the typed output this `SubTapestry` promises.

**Do this:**

```python
async def process(self, name: str, ...) -> Knot:
    agg = Aggregator(...)
    return _DatasetAssembler(batch=agg, name=name, ...)   # Assembler is the sink
```

**Not this:**

```python
# Wrong — process() must return a Knot, not a value
async def process(self, name: str, ...) -> DatasetPayload:
    agg = Aggregator(...)
    result = await self._run_inner(...)                   # do not call _run_inner
    return self._to_payload(result.outputs["agg"], name)  # do not post-process here
```

Reasons:
- Transformation logic in the graph means the inner run captures it in lineage, observability, and replay.
- The Assembler is reusable and testable as a standalone `Knot`.
- `_run_inner` and `result.outputs` are internal; `process()` should not touch them.

---

## 6. Inputs and wiring

`SubTapestry` inputs follow exactly the same rules as any `Knot`:

- A `Knot`-valued constructor argument becomes a **parent** — the outer engine resolves it before calling `process()`.
- A non-`Knot` argument becomes **config** — a constant available in `process()` as a plain value.
- `Knot | T` union annotations auto-coerce scalar values to `Parameter` nodes, giving them lineage.

Inside `process()`, all inputs arrive as resolved plain Python values. Use them to configure or conditionally include knots in the inner graph.

```python
# Outer tapestry:
upstream_label = LabelKnot(_config=KnotConfig(id="label"))
loader = MultiSourceLoader(
    label=upstream_label,       # Knot → parent; resolved before process() runs
    file_source=my_file_cfg,    # non-Knot → config constant
    _config=KnotConfig(id="loader"),
)

# Inside process():
async def process(self, label: str, file_source: FileSource | None, **_) -> Knot:
    # label is already resolved to a string
    # file_source is a plain FileSource (or None)
    ...
```

---

## 7. Error handling

**Inner pipeline failure**

If any knot in the inner tapestry raises an unhandled exception, `_run_inner` raises `SubTapestryError`. The base `__call__` catches it and returns `Err`, exactly like any other knot failure. The outer pipeline sees a normal failure and routes according to the outer knot's `error_policy`.

The `SubTapestryError` carries the inner `RunResult` as `.inner_result` — all inner exceptions are accessible from there.

**Sink validation failures**

Two guards run between `process()` returning and the inner graph executing:

- `process()` returned something that is not a `Knot` → `TypeError` with the class name and actual type.
- The returned `Knot` is not registered in the inner tapestry (built outside `process()`) → `ValueError`.

Both surface as `Err` to the outer pipeline.

**Within `process()` itself**

Any exception raised inside `process()` (before returning the sink) is caught by `__call__` and returned as `Err`. Write normal Python — no special error handling is needed.

---

## 8. Observability

The outer tapestry's history backend is captured at construction time and automatically injected into the inner tapestry at run time. Inner runs appear in the same history store as the outer run, linked by `parent_run_id` and `parent_knot_id`. The explorer's drill-down navigation follows these links — you can inspect the inner graph's per-knot outputs without any extra instrumentation.

If the `SubTapestry` is constructed outside a `with Tapestry():` block (e.g. dynamically mid-run), it falls back to the `_current_history` context var set by the enclosing `tapestry.run()` call.

---

## 9. Common mistakes

**Returning a value instead of a Knot**

```python
# Wrong
async def process(self, ...) -> Knot:
    agg = Aggregator(...)
    return agg.some_value    # AttributeError or wrong type
```

`process()` must return the `Knot` object itself, not its output. The base class runs it.

**Building the sink outside the process() body**

```python
# Wrong — sink_knot registered to a different Tapestry context
sink_knot = SomeKnot(_config=KnotConfig(id="sink"))

class MySubTapestry(SubTapestry):
    async def process(self, ...) -> Knot:
        return sink_knot    # raises ValueError: not registered in inner tapestry
```

All knots that will be part of the inner graph must be constructed inside `process()`.

**Calling `_run_inner` manually**

```python
# Wrong
async def process(self, ...) -> Knot:
    with Tapestry() as inner:    # do not open your own context
        sink = SomeKnot(...)
    result = await self._run_inner(inner)   # do not call this
    return result.outputs["sink"]
```

The base class manages the `Tapestry()` context and calls `_run_inner`. Opening your own context creates a separate, unlinked tapestry.

**Forgetting `**_: Any` on `process()`**

```python
# Wrong — Knot.__init_subclass__ enforces **_ on all process() signatures
async def process(self, name: str) -> Knot:   # raises TypeError at class definition time
    ...

# Correct
async def process(self, name: str, **_: Any) -> Knot:
    ...
```
