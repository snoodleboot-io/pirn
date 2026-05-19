# PRD: Map / ZipMap / DictMap Annotation API

Status: Complete | Completed: 2026-04-30

---

## Problem

The original `Map` was a wrapping knot — `Map(over=batch, each=analyse_sample, bind="sample", _config=...)` — with six identified problems:

1. The actual computation knot was invisible in the graph and lineage; only the wrapping `Map` appeared.
2. `bind` was stringly-typed — nothing enforced that `"sample"` matched a real parameter on the inner knot.
3. The `over` / `each` / `bind` meta-API was harder to read than a direct knot call.
4. No per-element observability — inner knots were ephemeral, constructed and called outside the tapestry.
5. Collection type handling was broken: sets iterate in undefined order (breaking content-addressed caching); dicts silently iterated over keys only; generators were fully materialised before any processing.
6. Inner knots could not have knot parents — only shared constants worked as inputs.

---

## Goal

Replace the wrapping-knot `Map` with input-site distribution annotations — `Map`, `ZipMap`, and `DictMap` — placed at wiring time on a knot's input arguments. The computation knot appears in the graph as itself. Collection type errors surface at construction or execution time with clear messages.

---

## Success Criteria (all met)

- `Map(knot)`, `ZipMap(knot)`, and `DictMap(knot)` are annotation markers in `pirn/nodes/map_markers.py` — not `Knot` subclasses.
- The computation knot appears in the tapestry graph and lineage under its own class name.
- `bind` string eliminated — parameter name is the binding, enforced by existing `process()` signature introspection.
- `MapTypeError` raised at execution time when input is a set or generator.
- `TypeError` raised at construction time when `Map` and `ZipMap` are mixed on the same knot, or when cross-product inputs (`Map(a)` and `Map(b)` on different parameters of the same knot) are detected.
- No engine changes required — `Knot.__init__` extracts `.source` from each marker; `Knot.__call__` fans out after `parent_results` is assembled.
- Old wrapping-knot `Map` in `pirn/nodes/map_.py` deleted.

---

## Scope

### In scope

- `Map`, `ZipMap`, `DictMap` annotation markers
- `MapTypeError` exception class
- Cross-product guard and mix guard at construction time
- Set and generator rejection at execution time
- Fan-out logic in `Knot.__init__` and `Knot.__call__`
- Deletion of old wrapping-knot `Map` (`pirn/nodes/map_.py`)
- Update `pirn/nodes/__init__.py` to export new marker classes
- Update internal usage (lab_batch example)

### Out of scope

- Per-element lineage (each element getting its own `KnotLineage` record) — deferred; all elements share the single knot's lineage record
- `DictMap` single-argument form (`item` receives `(key, value)` tuples) — deferred pending real usage signal
- Streaming / lazy collection support — deferred; significant engine work
- Nested `Map` — correct tool is `SubTapestry` inside a `Map`
