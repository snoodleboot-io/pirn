# Nodes

Specialised node classes beyond the base `Knot`.

| Class | Shape |
|-------|-------|
| `Source` | Zero parents → produces a value (file, DB query, fetch, etc.) |
| `Sink` | Terminal consumer; output conventionally `None` |
| `Aggregator` | N parents combined via a `combine` callable |
| `Branch` | One input + selector → tagged path; non-selected paths are skipped |
| `Gate` | One input + predicate → pass through or skip |
| `Map` | Wraps an inner knot, applying it per-element of a parent's list |
| `Reduce` | Folds a list parent into one value (whole-list or pairwise) |
| `SubTapestry` | A knot whose execution body is a complete inner tapestry pipeline |

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

## Map

::: pirn.nodes.map_.Map
    options:
      show_source: false
      members_order: source
      heading_level: 3

### Example

```python
from pirn import Map, KnotConfig

enriched = Map(
    over=record_ids_knot,    # produces list[str]
    each=enrich_record,      # applied to each element
    bind="record_id",        # name to bind each element to in process()
    _config=KnotConfig(id="enriched"),
)
```

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

**See also:** [`examples/pipeline_composition/sub_tapestry.py`](../../examples/pipeline_composition/sub_tapestry.py), [Visualization — SubTapestry drill-down](../guides/visualization.md#subtapestry-drill-down)
