`pirn.nodes` provides the structural knots that shape pipeline graphs — routing, fan-out, aggregation, iteration, and continuation — it does not perform domain work or I/O.

---

## Mental model

Every knot in `pirn.nodes` is a graph-shaping primitive. `Gate` and `Branch` control *which path* runs. `Map`, `ZipMap`, `DictMap`, and `Reduce` control *how many times* a knot runs over a collection. `Aggregator` merges multiple upstream values into one. `SubTapestry` and `LoopSubTapestry` encapsulate inner pipelines. `WithContinuation` spawns successor knots at run time from a pool. `Source` and `Sink` mark the entry and exit boundaries of a pipeline.

All of these are `Knot` subclasses and wire into a `Tapestry` context the same way as any other knot.

---

## Source map

```
pirn/nodes/
├── source.py            Source              — zero-parent entry knot; subclass and implement process(**_)
├── sink.py              Sink                — terminal consumer; return value is conventionally None
├── aggregator.py        Aggregator          — merge N parents via a combine callable
├── map_markers.py       Map                 — fan-out marker: invoke knot once per list element
│                        ZipMap              — fan-out marker: invoke knot once per zip of N lists
│                        DictMap             — fan-out marker: invoke knot once per dict entry (key+value)
├── reduce_.py           Reduce              — fold a list parent to a single value
├── gate/
│   └── gate.py          Gate                — pass input through if predicate is truthy; else Skipped
├── branch/
│   └── branch.py        Branch              — route one input to exactly one of N named output paths
├── continuation.py      WithContinuation    — run a knot then spawn successors from a pool at run time
│                        continues()         — convenience wrapper: attach a continuation to an existing knot
│                        Next                — dataclass describing one successor action + inputs
├── sub_tapestry.py      SubTapestry         — knot whose body is a complete inner tapestry; → see AGENTIC_USE.md in guides
└── loop_sub_tapestry.py LoopSubTapestry     — iterative SubTapestry; implement step() and fold()
```

---

## Canonical pattern

### Gate — block downstream on a condition

```python
from pirn import Tapestry, KnotConfig, RunRequest
from pirn.nodes.gate.gate import Gate

with Tapestry() as t:
    score  = ScoreKnot(_config=KnotConfig(id="score"))
    passed = Gate(input=score, predicate=lambda v: v >= 0.8, _config=KnotConfig(id="gate"))
    Notify(result=passed, _config=KnotConfig(id="notify"))   # skipped if score < 0.8
```

### Branch — route to different paths

```python
from pirn.nodes.branch.branch import Branch

with Tapestry() as t:
    classify = ClassifyKnot(_config=KnotConfig(id="classify"))
    router   = Branch(
        input=classify,
        selector=lambda label: label,          # must return one of the declared branch names
        branches=("approved", "rejected", "review"),
        _config=KnotConfig(id="router"),
    )
    HandleApproved(item=router["approved"],  _config=KnotConfig(id="ok"))
    HandleRejected(item=router["rejected"],  _config=KnotConfig(id="no"))
    HandleReview(  item=router["review"],    _config=KnotConfig(id="rev"))
```

### Map — fan a knot over a list

```python
from pirn.nodes.map_markers import Map

with Tapestry() as t:
    rows    = LoadRows(_config=KnotConfig(id="load"))
    # ScoreRow.process receives one row at a time; output is list[float]
    scores  = ScoreRow(row=Map(rows), _config=KnotConfig(id="score"))
    summary = Summarise(scores=scores, _config=KnotConfig(id="summary"))
```

### ZipMap — parallel fan-out over two lists element-wise

```python
from pirn.nodes.map_markers import ZipMap

with Tapestry() as t:
    texts  = LoadTexts(_config=KnotConfig(id="texts"))
    labels = LoadLabels(_config=KnotConfig(id="labels"))
    # Evaluate.process receives one (text, label) pair at a time
    scored = Evaluate(text=ZipMap(texts), label=ZipMap(labels), _config=KnotConfig(id="eval"))
```

### DictMap — fan over dict entries

```python
from pirn.nodes.map_markers import DictMap

with Tapestry() as t:
    config  = LoadConfig(_config=KnotConfig(id="cfg"))
    # Validate.process receives (key, value) for each config entry
    results = Validate(key=DictMap(config), value=DictMap(config), _config=KnotConfig(id="val"))
```

### Aggregator — merge multiple upstreams

```python
from pirn.nodes.aggregator import Aggregator

with Tapestry() as t:
    a = SourceA(_config=KnotConfig(id="a"))
    b = SourceB(_config=KnotConfig(id="b"))
    merged = Aggregator(
        combine=lambda a, b: {**a, **b},
        a=a, b=b,
        _config=KnotConfig(id="merge"),
    )
```

### Reduce — fold a list to one value

```python
from pirn.nodes.reduce_ import Reduce

with Tapestry() as t:
    scores = ScoreAll(_config=KnotConfig(id="scores"))   # produces list[float]
    total  = Reduce(of=scores, combine=lambda acc, x: acc + x, initial=0.0,
                    _config=KnotConfig(id="total"))
```

---

## Anti-patterns

### Accessing `branch["name"]` outside the `with Tapestry()` block

`branch["name"]` looks up a `BranchOutput` knot that was registered at `Branch` construction time. Accessing it after the `with` block closes still works — the knot exists — but constructing downstream knots that reference it outside the block means they are never registered in any tapestry. Build the full graph inside one `with Tapestry()` block.

### Mixing `Map`, `ZipMap`, or `DictMap` on the same knot

A knot may use only one marker type across all its inputs. Mixing (e.g. `row=Map(rows), label=ZipMap(labels)`) raises `MapTypeError` at construction time.

### Passing a non-`Knot` to `Gate` or `Branch`

Both require `input` to be a `Knot` instance. Passing a plain value raises `TypeError` at construction — unlike most knot parameters, these cannot auto-coerce to `Parameter` because the fan-out / routing semantics require a resolved runtime value.

### Using `Reduce` pairwise form without `initial`

If `combine` takes two arguments (pairwise form) and `initial` is not supplied, `TypeError` is raised at construction. An empty list input with no `initial` has no defined result.

### Returning a non-list from a `Map` source

The `Map` marker expects the source knot to produce a `list` or `tuple` at run time. If it produces any other type, the engine raises `MapTypeError` at execution time — not construction time. Verify output types before wiring fan-out.

---

## Constraints and gotchas

- **`Gate` converts `Err` to `Skipped`, not the other way.** A closed gate produces `Skipped`, not `Err`. Downstream knots with `SKIP_IF_PARENT_FAILED` policy are skipped — not failed.
- **`Branch` registers N companion `BranchOutput` knots automatically.** They get ids `{branch_id}:{name}`. These appear in `result.outputs` and lineage records.
- **`Aggregator.combine` may be async.** Both sync and async callables are supported and detected automatically at construction.
- **`WithContinuation` requires an extensible tapestry.** It calls `get_current_store()` to register successors mid-run. Use `tapestry.run(extensible=True)` — only the `InMemoryStore` backend supports this.
- **`continues(knot, fn=..., pool=...)` is syntactic sugar.** It wraps `knot` in a `WithContinuation` and returns the wrapper. The original knot id is preserved as the wrapped parent.
- **`Sink` has no enforcement on return type.** The `None` convention is by contract, not by runtime check. Downstream knots wired to a `Sink` will receive `None`.

---

## Quick reference

| Task | How |
|------|-----|
| Block downstream on a condition | `Gate(input=knot, predicate=fn, _config=...)` |
| Route to one of N paths | `Branch(input=knot, selector=fn, branches=(...), _config=...)` then wire `branch["name"]` |
| Fan a knot over a list | `MyKnot(item=Map(list_knot), _config=...)` |
| Fan over two lists element-wise | `MyKnot(a=ZipMap(ka), b=ZipMap(kb), _config=...)` |
| Fan over dict key+value | `MyKnot(key=DictMap(d), value=DictMap(d), _config=...)` |
| Merge N upstreams | `Aggregator(combine=fn, a=ka, b=kb, _config=...)` |
| Fold a list to one value | `Reduce(of=list_knot, combine=fn, initial=v, _config=...)` |
| Define a pipeline entry point | `class MySource(Source): async def process(self, **_) -> T` |
| Define a pipeline terminal | `class MySink(Sink): async def process(self, data: T, **_) -> None` |
| Spawn successors at run time | `continues(knot, fn=continuation_fn, pool={"action": KnotClass})` |
| Inner pipeline as one node | subclass `SubTapestry` — see [guides/sub-tapestry.md](../../docs/guides/sub-tapestry.md) |
| Iterative / agentic loop | subclass `LoopSubTapestry[S]` — see [guides/agentic-loops.md](../../docs/guides/agentic-loops.md) |

---

*See also: [pirn AGENTIC_USE.md](../../AGENTIC_USE.md)*
