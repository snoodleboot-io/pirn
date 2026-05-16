# ADR-003: Map / ZipMap / DictMap — Annotation-Based Fan-Out

**Status:** Accepted
**Date:** 2026-04-30
**Branch:** feat/map-redesign
**Source:** planning/archive/map-redesign-ard.md

---

## Context

The original `Map` was a wrapping knot:

```python
Map(over=batch, each=analyse_sample, bind="sample", _config=KnotConfig(id="analyse"))
```

Six problems were identified during design review:

1. The actual computation knot (`analyse_sample`) was invisible in the graph and lineage — only `Map` appeared.
2. `bind` was stringly-typed — nothing enforced that `"sample"` matched a real parameter on `analyse_sample`.
3. `over`, `each`, `bind` is a meta-API wrapping the computation, not a readable call site.
4. No per-element observability — inner knots were ephemeral, constructed and called outside the tapestry.
5. Collection type handling was broken — sets iterate in undefined order (breaking content-addressed caching); dicts silently iterate over keys only; generators were fully materialised before any processing.
6. Inner knots could not have knot parents — only shared constants worked.

---

## Decision

Replace the wrapping-knot `Map` with **input-site distribution annotations**: `Map`, `ZipMap`, and `DictMap`. These are not knots — they are markers placed at wiring time on a knot's input arguments.

```python
# Before
Map(over=batch, each=analyse_sample, bind="sample", _config=KnotConfig(id="analyse"))

# After
analyse_sample(sample=Map(batch), _config=KnotConfig(id="analyse"))
```

`analyse_sample` appears in the graph and lineage as itself. Its `process(sample: RawSample)` signature is typed for a single element. The `Map(batch)` annotation instructs the engine to fan the knot out over the collection at execution time, producing `list[output]`.

**The three markers** (in `pirn/nodes/map_markers.py`, not `Knot` subclasses):

| Marker | Source type | Semantics |
|--------|-------------|-----------|
| `Map(knot)` | `list` or `tuple` | Ordered sequence — concurrent via `asyncio.gather`, output order preserved |
| `ZipMap(knot)` | `list` or `tuple` | Multiple collections, element-wise — all `ZipMap` inputs on one knot zipped together |
| `DictMap(knot)` | `dict` | Key-value pairs — both `key` and `value` inputs must reference same source knot |

**Rules enforced at construction:**
- Mixing `Map` and `ZipMap` on the same knot is a `TypeError`
- Cross-product (`Map(a)` and `Map(b)` on different inputs of same knot) is a `TypeError`
- Sets and generators raise `MapTypeError` at execution time — undefined iteration order breaks content-addressed caching

**Engine changes:** None. `Knot.__init__` extracts the `.source` from each marker and registers it as a parent. `Knot.__call__` fans out after `parent_results` is assembled. The engine calls `__call__` exactly as today and receives `Ok(list[T])`.

**Old wrapping-knot `Map`** in `pirn/nodes/map_.py` is deleted. `pirn/nodes/__init__.py` exports the new marker classes instead.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| Keep wrapping-knot `Map`, fix the individual problems | Each fix (observability, type safety, collection validation) would require invasive changes to the meta-API. The annotation model solves all six problems with a cleaner surface. |
| Engine-level fan-out (a special knot type the engine recognises) | Requires engine changes and special cases in the topological sort — more complexity than a wiring-time marker. |
| Nested `Map` support | Deferred explicitly — the correct tool for "a collection where each element is itself a multi-step pipeline" is `SubTapestry` inside a `Map`, which gives per-element inner lineage and drill-down. |

---

## Consequences

**Positive:**
- The actual knot class appears in the graph and lineage — full observability.
- `bind` string eliminated — parameter name is the binding, enforced by existing `process()` signature introspection.
- Collection type errors surface early with clear messages.
- `analyse_sample(sample=Map(batch), ...)` is self-explanatory at the call site.
- `ZipMap` makes multi-collection intent explicit and prevents the cross-product footgun.
- No engine changes required.

**Negative / Risks:**
- `Knot.__init__` and `Knot.__call__` gain additional code paths — both require careful test coverage.
- Per-element lineage (each element getting its own `KnotLineage` record) is still absent. All elements share the single knot's lineage record. Tracked as a future phase.
- Existing code using the wrapping `Map` breaks. The lab_batch example was the only internal usage and was updated.

---

## Deferred

- **Per-element lineage** — each element getting its own `KnotLineage` record; requires engine changes and schema migration.
- **`DictMap` single-argument form** — `process_entry(item=DictMap(lookup))` where `item` receives `(key, value)` tuples; deferred pending real usage signal.
- **Streaming / lazy collections** — processing generator output without full materialisation; significant engine work.
