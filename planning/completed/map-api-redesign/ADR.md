# ADR: Map / ZipMap / DictMap — Annotation-Based Fan-Out

Status: Accepted | Date: 2026-04-30

---

## Context

The original `Map` was a wrapping knot that accepted `over=`, `each=`, and `bind=` arguments and ran the inner knot invisibly. Six problems were identified: (1) the computation knot was invisible in the graph and lineage, (2) `bind` was stringly-typed, (3) the meta-API was hard to read, (4) no per-element observability, (5) broken collection type handling (sets, dicts, generators), and (6) inner knots could not have knot parents.

---

## Decision

Replace the wrapping-knot `Map` with **input-site distribution annotations**: `Map`, `ZipMap`, and `DictMap`. These are not knots — they are markers placed at wiring time on a knot's input arguments. The computation knot appears in the graph as itself.

```python
# Before
Map(over=batch, each=analyse_sample, bind="sample", _config=KnotConfig(id="analyse"))

# After
analyse_sample(sample=Map(batch), _config=KnotConfig(id="analyse"))
```

The three markers (in `pirn/nodes/map_markers.py`):

| Marker | Source type | Semantics |
|--------|-------------|-----------|
| `Map(knot)` | `list` or `tuple` | Ordered sequence — concurrent via `asyncio.gather`, output order preserved |
| `ZipMap(knot)` | `list` or `tuple` | Multiple collections, element-wise — all `ZipMap` inputs zipped together |
| `DictMap(knot)` | `dict` | Key-value pairs — both `key` and `value` inputs must reference same source knot |

Rules enforced at construction:
- Mixing `Map` and `ZipMap` on the same knot → `TypeError`
- Cross-product (two `Map` inputs on different parameters of same knot) → `TypeError`

Rules enforced at execution:
- Sets and generators → `MapTypeError` (undefined iteration order breaks content-addressed caching)

No engine changes required. `Knot.__init__` extracts `.source` from each marker and registers it as a parent. `Knot.__call__` fans out after `parent_results` is assembled and returns `Ok(list[T])`. The old wrapping-knot `Map` in `pirn/nodes/map_.py` is deleted.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| Keep wrapping-knot `Map`, fix individual problems | Each fix (observability, type safety, collection validation) required invasive changes to the meta-API. The annotation model solves all six problems with a cleaner surface. |
| Engine-level fan-out (special knot type the engine recognises) | Requires engine changes and special cases in topological sort — more complexity than a wiring-time marker. |
| Nested `Map` support | Deferred — correct tool is `SubTapestry` inside a `Map`, giving per-element inner lineage and drill-down. |

---

## Consequences

**Positive:**
- The actual knot class appears in the graph and lineage — full observability.
- `bind` string eliminated — parameter name is the binding, enforced by `process()` signature introspection.
- Collection type errors surface early with clear messages.
- `analyse_sample(sample=Map(batch), ...)` is self-explanatory at the call site.
- `ZipMap` makes multi-collection intent explicit and prevents the cross-product footgun.
- No engine changes required.

**Negative:**
- `Knot.__init__` and `Knot.__call__` gain additional code paths — both require careful test coverage.
- Per-element lineage (each element getting its own `KnotLineage` record) is still absent — tracked as a future phase.
- Existing code using the wrapping `Map` breaks. The lab_batch example was the only internal usage and was updated.
