# Nodes

Specialised node classes beyond the base `Knot`.

| Class | Shape |
|-------|-------|
| `Source` | Zero parents → produces a value (file, DB query, fetch, etc.) |
| `Sink` | Terminal consumer; output conventionally `None` |
| `Aggregator` | N parents combined via a `combine` callable |
| `Branch` | One input + selector → tagged path; non-selected paths are skipped |
| `Gate` | One input + predicate → pass through or skip |
| `Map` | Distribute a knot over an ordered collection (list/tuple) |
| `ZipMap` | Distribute a knot over multiple collections element-wise |
| `DictMap` | Distribute a knot over the entries of a dict |
| `Reduce` | Folds a list parent into one value (whole-list or pairwise) |
| `SubTapestry` | A knot whose execution body is a complete inner tapestry pipeline |
| `WithContinuation` | Wraps a knot and spawns successors based on its output at runtime |
| `LoopSubTapestry` | Iterative SubTapestry: iterations as knots in one extensible run |

---

## Source

::: pirn.nodes.source.Source
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## Sink

::: pirn.nodes.sink.Sink
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## Aggregator

::: pirn.nodes.aggregator.Aggregator
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn import Aggregator, KnotConfig

merged = Aggregator(
    parents={"left": left_knot, "right": right_knot},
    combine=lambda d: {**d["left"], **d["right"]},
    _config=KnotConfig(id="merged"),
)
```

---

## Branch

::: pirn.nodes.branch.branch.Branch
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn import Branch, KnotConfig

route = Branch(
    input=classify_knot,
    selector=lambda msg: msg["type"],
    branches=("tool_call", "response", "error"),
    _config=KnotConfig(id="route"),
)

# Access branch outputs — non-selected paths produce Skipped
handle_tool(payload=route["tool_call"], _config=KnotConfig(id="handle_tool"))
handle_resp(payload=route["response"], _config=KnotConfig(id="handle_resp"))
```

**See also:** `examples/financial/loan_underwriting.py` — Branch + Aggregator for loan underwriting track routing.

---

## Gate

::: pirn.nodes.gate.gate.Gate
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn import Gate, KnotConfig

quality_gate = Gate(
    input=score_knot,
    predicate=lambda score: score > 0.8,
    _config=KnotConfig(id="quality_gate"),
)

# Only runs if score > 0.8
publish(data=quality_gate, _config=KnotConfig(id="publish"))
```

---

## Map / ZipMap / DictMap

Distribution markers placed at wiring time on a knot's input arguments.
They are **not knots** — they are plain Python objects that instruct the
engine to fan a knot out over a collection.  The annotated knot appears in
the graph and lineage as itself; its `process` signature is typed for a
single element.

::: pirn.nodes.map_markers.Map
    options:
      show_source: false
      heading_level: 3

::: pirn.nodes.map_markers.ZipMap
    options:
      show_source: false
      heading_level: 3

::: pirn.nodes.map_markers.DictMap
    options:
      show_source: false
      heading_level: 3

### Example

```python
from pirn.nodes.map_markers import Map, ZipMap, DictMap
from pirn import KnotConfig

# Map: fan over a single ordered collection
analysed = analyse_sample(sample=Map(batch), _config=KnotConfig(id="analyse"))

# ZipMap: zip two collections element-wise
result = process_pair(a=ZipMap(knot_a), b=ZipMap(knot_b), _config=KnotConfig(id="pairs"))

# DictMap: iterate over dict entries (first annotated input = key, second = value)
entries = process_entry(k=DictMap(lookup), v=DictMap(lookup), _config=KnotConfig(id="entries"))
```

**Rules:**
- `Map` requires a `list` or `tuple`; any other type raises `MapTypeError`.
- Multiple `Map` annotations on different inputs of the same knot is a
  construction-time `TypeError` (cross-product).
- `Map` and `ZipMap` cannot be mixed on the same knot.
- Both `DictMap` inputs must reference the same source knot.
- Output type is always `list[T]`.

**See also:** `examples/lab_batch/lab_batch.py` — batch pathology sample processing with chained Maps.

---

## Reduce

::: pirn.nodes.reduce_.Reduce
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn import Reduce, KnotConfig

total = Reduce(
    of=scores_knot,    # produces list[float]
    combine=sum,       # whole-list combine
    _config=KnotConfig(id="total"),
)
```

---

## SubTapestry

A knot whose execution body is a complete inner tapestry pipeline. Use it when a single logical step in your outer pipeline is itself a multi-step workflow — validation, fulfillment, scoring, enrichment — that you want independently versioned, cached, and inspectable.

Subclass `SubTapestry` and implement `process(**kwargs)`. Inside `process`, construct an inner `Tapestry`, build the pipeline, and return `await self._run_inner(inner_tapestry)`.

The outer tapestry's history backend is automatically forwarded to inner runs so they land in the same store and are reachable via the explorer's drill-down navigation.

::: pirn.nodes.sub_tapestry.SubTapestry
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn.nodes.sub_tapestry import SubTapestry
from pirn import KnotConfig
from pirn.tapestry import Tapestry
from pirn.core.parameter import Parameter
from pirn.core.run_result import RunResult

class ValidateOrder(SubTapestry):
    async def process(self, order: Order, **_) -> RunResult:
        with Tapestry() as inner:
            p = Parameter("order", Order, default=order, _config=KnotConfig(id="order"))
            check_inventory(order=p, _config=KnotConfig(id="inventory"))
            authorize_payment(order=p, _config=KnotConfig(id="payment"))
        return await self._run_inner(inner)

# Wire into an outer tapestry like any other knot
with Tapestry() as t:
    order = Parameter("order", Order, _config=KnotConfig(id="order"))
    validated = ValidateOrder(
        order=order,
        _config=KnotConfig(id="validate", validate_io=False),
    )
```

### Using SubTapestry from YAML

The outer topology can be declared in YAML by referencing the subclass by its dotted import path. The inner pipeline logic stays in `process()` in Python.

```yaml
nodes:
  - id: order
    type: parameter
    type_: examples.pipeline_composition.sub_tapestry.Order

  - id: validate
    type: knot
    callable: examples.pipeline_composition.sub_tapestry.ValidateOrder
    parents:
      order: order
```

### Error handling

If the inner run produces any exceptions, `_run_inner` raises `SubTapestryError`. The outer engine catches this and records the knot as `Err`, with the inner `RunResult` attached for inspection:

```python
from pirn.nodes.sub_tapestry import SubTapestryError

try:
    result = await tapestry.run(request)
except SubTapestryError as e:
    print(e.inner_result.exceptions)
```

**See also:** `examples/pipeline_composition/sub_tapestry.py`, [Visualization — SubTapestry drill-down](../guides/visualization.md#subtapestry-drill-down)

---

## WithContinuation / continues()

Attaches dynamic next-step logic to any knot without modifying it. The continuation is a plain function that receives the knot's output and returns a `list[Next]` — one entry per successor to spawn into the running extensible tapestry. Always returns at least one entry; use `Next("end")` to terminate explicitly.

```python
from pirn.nodes.continuation import Next, continues

POOL = {
    "summarise": SummariseKnot,
    "web_search": WebSearchKnot,
}

def router(result: SearchResult) -> list[Next]:
    if result.confidence < 0.6:
        return [Next("web_search", {"query": result.original_query})]
    return [Next("summarise", {"text": result.content})]

search = WebSearchKnot(query=q, _config=KnotConfig(id="search"))
continues(search, fn=router, pool=POOL)
```

`continues()` returns a `WithContinuation` knot wired immediately after the wrapped knot. Must be used inside an extensible tapestry run — in a non-extensible run the continuation fires but spawned knots are silently dropped.

`Next` fields:

| Field | Type | Description |
|-------|------|-------------|
| `action` | `str` | Key in the pool, or `"end"` for the built-in terminal |
| `inputs` | `dict` | Constructor kwargs for the spawned knot |
| `id` | `str \| None` | Override auto-generated knot id |

---

## LoopSubTapestry

An iterative `SubTapestry` where all iterations execute as knots within a single extensible inner run, connected by real data edges. Use when the number of iterations is unknown until runtime and each iteration's structure may depend on the previous result.

Subclass and implement:

- **`step(state) -> tuple[Tapestry, S] | None`** — plan the next iteration's inner graph. Return `None` to terminate.
- **`fold(state, result) -> S`** — integrate the iteration's `RunResult` into state.
- **`step_id(state, idx) -> str`** — optional; override for domain-meaningful iteration knot IDs (default: `step_{idx}`).

```python
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.tapestry import Tapestry
from pirn.core.knot_config import KnotConfig

class Refiner(LoopSubTapestry[RefinementState]):

    def step(self, state: RefinementState) -> tuple[Tapestry, RefinementState] | None:
        if state.converged or state.rounds >= MAX_ROUNDS:
            return None
        state.rounds += 1
        with Tapestry() as t:
            RefineKnot(data=state.current, _config=KnotConfig(id="refine"))
        return t, state

    def fold(self, state: RefinementState, result: RunResult) -> RefinementState:
        state.current = result.outputs["refine"]
        state.converged = _has_converged(state.current)
        return state

    def step_id(self, state: RefinementState, idx: int) -> str:
        return f"refine_round_{idx}"
```

Each iteration is a knot in one loop run; the knots are chained by real parent edges so lineage and the explorer reflect the true sequential (or parallel) execution history. Drill into any iteration knot to see its inner tapestry.

**See also:** `examples/llm_agent/agent_loop.py` — dynamic DAG agent loop built on extensible tapestry and `get_current_store()`.
