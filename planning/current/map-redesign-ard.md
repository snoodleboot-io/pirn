# ARD: Map / ZipMap / DictMap — Input-Annotation Distribution API

**Status:** Accepted  
**Author:** John Aven  
**Date:** 2026-04-30  
**Branch:** feat/map-redesign  
**Replaces:** `pirn.nodes.map_.Map` (wrapping-knot design)

---

## 1. Context

The current `Map` is a wrapping knot:

```python
Map(over=batch, each=analyse_sample, bind="sample", _config=KnotConfig(id="analyse"))
```

It has the following problems identified during design review:

1. **The actual computation is invisible.** The graph and lineage show a `Map` node, not `analyse_sample`. There is no record of what knot class ran per element.
2. **`bind` is stringly-typed.** Nothing enforces that `"sample"` matches a real parameter on `analyse_sample`. Type errors surface at runtime, not at wiring.
3. **`over`, `each`, `bind` is a meta-API** wrapped around the computation. The user cannot read it as "call `analyse_sample` with `sample` mapped over `batch`."
4. **No per-element observability.** Inner knots are ephemeral; they are constructed and called outside the tapestry. No lineage, no explorer visibility.
5. **Collection type handling is broken.** Sets iterate in undefined order, breaking content-addressed caching. Dicts silently iterate over keys only. Generators are materialised entirely before any processing begins.
6. **Inner knots cannot have knot parents.** Only shared constants work; a per-element knot that depends on another knot upstream cannot be expressed.

---

## 2. Decision

Replace the wrapping-knot `Map` with **input-site distribution annotations**: `Map`, `ZipMap`, and `DictMap`. These are **not knots** — they are markers placed at wiring time on a knot's input arguments.

```python
# Before
Map(over=batch, each=analyse_sample, bind="sample", _config=KnotConfig(id="analyse"))

# After
analyse_sample(sample=Map(batch), _config=KnotConfig(id="analyse"))
```

The `analyse_sample` knot appears in the graph and lineage as itself. Its `process(sample: RawSample)` signature is typed for a single element. The `Map(batch)` annotation on the `sample` argument instructs the engine to fan the knot out over the collection at execution time, producing `list[output]`.

---

## 3. The Three Markers

### 3.1 `Map(knot)` — ordered sequence

```python
analyse_sample(sample=Map(batch), _config=KnotConfig(id="analyse"))
```

- `batch` must produce a `list` or `tuple`. Any other type raises `MapTypeError` at execution time with a clear message.
- Elements are processed concurrently via `asyncio.gather`.
- Output type is `list[T]` where `T` is the return type of `process`.
- If any element raises, the knot produces `Err`. There is no partial-success list.
- The output list preserves input order regardless of which element finishes first.

### 3.2 `ZipMap(knot)` — multiple collections, element-wise

```python
process_pair(a=ZipMap(knot_a), b=ZipMap(knot_b), _config=KnotConfig(id="pairs"))
```

- All `ZipMap`-annotated inputs on a single knot construction are treated as a coordinated zip group.
- Collections are zipped to the length of the shortest (Python `zip` semantics).
- `process(a, b)` is called once per pair — types match the single-element signatures.
- Output type is `list[T]`.
- Mixing `Map` and `ZipMap` on the same knot is a construction-time `TypeError`.

### 3.3 `DictMap(knot)` — key-value pairs

```python
process_entry(key=DictMap(lookup), value=DictMap(lookup), _config=KnotConfig(id="entries"))
```

- `lookup` must produce a `dict`. Any other type raises `MapTypeError`.
- Both `key` and `value` must reference the same source knot (enforced at construction). The framework zips `dict.keys()` to `key` and `dict.values()` to `value`.
- Alternatively, a single-argument form passes a `(key, value)` tuple per entry — TBD during implementation.
- Iteration order follows insertion order (Python 3.7+ dict guarantee).
- Output type is `list[T]`.

---

## 4. What Is Explicitly Ruled Out

### 4.1 Cross-product

`Map(a)` and `Map(b)` on different inputs of the same knot would mean `|a| × |b|` executions. This is almost never correct in a pipeline and would be a silent footgun. It is a construction-time `TypeError`: "use ZipMap for multi-collection distribution."

### 4.2 Nested Map

Using `Map` inside a `Map`-distributed knot's process body is not a supported pattern. The correct tool for "a collection where each element is itself a multi-step pipeline" is `SubTapestry` inside a `Map`. This gives per-element inner lineage, isolation, and drill-down in the explorer — things nested `Map` could not provide.

### 4.3 Sets and generators as source collections

`Map` requires `list` or `tuple`. Sets have undefined iteration order, which breaks content-addressed caching (same set, different run → different output hash). Generators are lazy and may not be replayable. Both raise `MapTypeError` with an explanation. Users who genuinely need set semantics should sort into a list upstream.

---

## 5. Implementation

### 5.1 Marker classes

Three lightweight classes in `pirn/nodes/map_markers.py`:

```python
class Map:
    def __init__(self, source: Knot) -> None: ...

class ZipMap:
    def __init__(self, source: Knot) -> None: ...

class DictMap:
    def __init__(self, source: Knot) -> None: ...
```

None of these are `Knot` subclasses. They are plain Python objects used only at wiring time.

### 5.2 `Knot.__init__` changes

`Knot.__init__` currently classifies kwargs as either `parents` (Knot-valued) or `config_values` (non-Knot). The new logic:

1. Before the existing classification, scan kwargs for `Map`, `ZipMap`, or `DictMap` instances.
2. Extract the `.source` knot from each marker and register it as a parent under the same name.
3. Store the set of mapped input names on `_mutable_mapped_inputs: dict[str, type[Map | ZipMap | DictMap]]`.
4. Validate that no knot mixes `Map` and `ZipMap`, and that `ZipMap` on a single input has a counterpart on at least one other input.

### 5.3 `Knot.__call__` changes

After `parent_results` is assembled but before `process()` is called:

1. Check `_mutable_mapped_inputs`. If empty, proceed as today.
2. Extract the collection(s) from `parent_results` for mapped inputs.
3. Validate collection types (list/tuple for `Map`/`ZipMap`, dict for `DictMap`). Raise `MapTypeError` if wrong.
4. Build a list of per-element `kwargs` dicts by zipping/iterating the collections.
5. `asyncio.gather` N calls to `self.process(**element_kwargs)` concurrently.
6. Collect results into `list`, preserving order. If any element returns `Err`, the whole knot returns `Err`.
7. Return `Ok(list_of_outputs)`.

No engine changes required. The engine calls `__call__` exactly as today and receives `Ok(list[T])`.

### 5.4 Tapestry graph / scanner

The knot appears in the graph as its own class (`analyse_sample`, not `Map`). The edge from `batch` to `analyse_sample` is annotated with a `*` suffix on the label (e.g. `sample*`) to signal distribution in the explorer. `_scanner.py` reads this from the edge label; no schema changes required.

### 5.5 Old `Map` removal

The wrapping-knot `Map` class in `pirn/nodes/map_.py` is deleted. `pirn/nodes/__init__.py` exports the new marker classes instead. The lab_batch example is updated to use the new API.

---

## 6. Consequences

**Positive:**
- The actual knot class appears in the graph and lineage — full observability.
- `bind` string eliminated — parameter name is the binding, enforced by the existing `process()` signature introspection.
- Collection type errors surface early with clear messages rather than silent misbehaviour.
- Reading `analyse_sample(sample=Map(batch), ...)` is self-explanatory.
- `**_` works exactly as everywhere else — no special convention for Map knots.
- `ZipMap` makes multi-collection intent explicit and prevents the cross-product footgun.

**Negative / Risks:**
- `Knot.__init__` and `Knot.__call__` get more complex — two carefully tested code paths.
- Per-element lineage is still absent (all elements share the single knot's lineage record). This is a Phase 2 concern; the ARD does not address it.
- Existing code using the wrapping `Map` breaks. The lab_batch example is the only internal usage; external consumers would need a migration.

---

## 7. Deferred

- **Per-element lineage** — each element getting its own `KnotLineage` record. Requires engine changes and a schema migration. Tracked separately.
- **`DictMap` single-argument form** — `process_entry(item=DictMap(lookup))` where `item` receives `(key, value)` tuples. Deferred pending real usage signal.
- **Streaming / lazy collections** — processing generator output without full materialisation. Significant engine work; deferred.
