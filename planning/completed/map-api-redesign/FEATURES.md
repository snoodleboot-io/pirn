# Features: Map / ZipMap / DictMap Annotation API

---

## Feature: Map / ZipMap / DictMap Annotation Markers

Replace the wrapping-knot `Map` with three input-site annotation markers. The computation knot appears in the tapestry graph as itself; fan-out semantics are declared at the wiring call site.

### Story: Pipeline authors can distribute a knot over a list without a wrapping knot

As a pipeline author, I can write `analyse_sample(sample=Map(batch), _config=...)` so that `analyse_sample` appears in the graph and lineage under its own name, and the fan-out intent is visible at the call site.

#### Tasks

- Create `pirn/nodes/map_markers.py` — implement `Map`, `ZipMap`, and `DictMap` marker classes (not `Knot` subclasses)
- Each marker stores `.source` (the upstream knot) and is recognized by `Knot.__init__`
- Update `pirn/nodes/__init__.py` to export `Map`, `ZipMap`, `DictMap`, and `MapTypeError` in place of the old wrapping-knot `Map`
- Delete `pirn/nodes/map_.py` — old wrapping-knot `Map`

### Story: Pipeline authors can zip multiple collections element-wise across a single knot

As a pipeline author, I can write `process_pair(left=ZipMap(lefts), right=ZipMap(rights), _config=...)` so that corresponding elements of `lefts` and `rights` are paired per invocation rather than cross-producted.

#### Tasks

- Implement `ZipMap` marker in `pirn/nodes/map_markers.py`
- Enforce in `Knot.__init__` that all `ZipMap` inputs on a single knot reference collections of the same declared length
- Raise `TypeError` at construction when `Map` and `ZipMap` are mixed on the same knot

### Story: Pipeline authors can distribute a knot over a dict's key-value pairs

As a pipeline author, I can write `lookup(key=DictMap(table, "key"), value=DictMap(table, "value"), _config=...)` so that each key-value pair in `table` produces one invocation.

#### Tasks

- Implement `DictMap` marker in `pirn/nodes/map_markers.py`
- Enforce in `Knot.__init__` that both `key` and `value` `DictMap` inputs on a single knot reference the same source knot

---

## Feature: Engine Fan-Out Support

Wire fan-out logic into `Knot.__init__` (parent registration) and `Knot.__call__` (execution) so that no engine changes are required. The engine calls `__call__` exactly as today and receives `Ok(list[T])`.

### Story: The tapestry engine does not need special cases for map knots

As a framework maintainer, I can add fan-out support by modifying only `Knot.__init__` and `Knot.__call__` so that the topological sort and execution model remain unchanged.

#### Tasks

- Update `Knot.__init__` to detect marker inputs, extract `.source` from each marker, and register the source as a parent knot
- Update `Knot.__call__` to fan out after `parent_results` is assembled: iterate the source collection, call `process()` for each element, collect results via `asyncio.gather`, and return `Ok(list[T])`
- Update internal lab_batch example to use the new annotation form
- Write tests covering: single `Map`, `ZipMap` with two collections, `DictMap` with a dict source

---

## Feature: Error Handling (MapTypeError, Cross-Product Guard, Mix Guard)

Raise construction-time and execution-time errors with clear messages for all invalid fan-out configurations. Prevent undefined-order iteration from silently corrupting content-addressed caches.

### Story: Pipeline authors receive a clear error when they accidentally cross-product two Map inputs

As a pipeline author, if I accidentally write `f(a=Map(xs), b=Map(ys), _config=...)`, I receive a `TypeError` at construction time explaining that cross-product is not supported — not a silent Cartesian explosion at runtime.

#### Tasks

- Implement cross-product guard in `Knot.__init__`: raise `TypeError` when two or more `Map` inputs reference different source knots on the same knot

### Story: Pipeline authors receive a clear error when they mix Map and ZipMap on the same knot

As a pipeline author, if I accidentally write `f(a=Map(xs), b=ZipMap(ys), _config=...)`, I receive a `TypeError` at construction time explaining that `Map` and `ZipMap` cannot be mixed.

#### Tasks

- Implement mix guard in `Knot.__init__`: raise `TypeError` when both `Map` and `ZipMap` markers are present on the same knot

### Story: Pipeline authors receive a clear error when they pass a set or generator to Map

As a pipeline author, if I pass a `set` or generator as the source collection, I receive a `MapTypeError` at execution time explaining that undefined iteration order breaks content-addressed caching.

#### Tasks

- Implement `MapTypeError(TypeError)` in `pirn/nodes/map_markers.py`
- Raise `MapTypeError` in `Knot.__call__` when the resolved source value is a `set` or generator at execution time
- Include the source knot name and parameter name in the error message
