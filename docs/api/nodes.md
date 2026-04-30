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
