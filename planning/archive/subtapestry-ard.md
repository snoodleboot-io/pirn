# ARD: SubTapestry Knot — Architecture Decision Record

**Status:** Complete  
**Author:** John Aven  
**Date:** 2026-04-30  
**Branch:** feat/subtapestry-knot  
**Related PRD:** planning/current/subtapestry-prd.md

---

## 1. Context

pirn pipelines are flat graphs. Every knot lives in the same tapestry namespace. There is no way to encapsulate a sub-pipeline as a reusable, composable unit of work. `SubTapestry` introduces that concept: a knot whose execution body is a complete inner tapestry pipeline.

---

## 2. Core Design Decisions

### 2.1 SubTapestry has a `process()` — it is not knotless

The user subclasses `SubTapestry` and implements `process(**kwargs)`. Inside `process`, they build and run an inner `Tapestry`. The framework does not require the inner tapestry to be pre-built and passed at construction — it is constructed fresh on each execution, with the already-resolved input values available as plain Python values.

```python
class ScorePipeline(SubTapestry):
    async def process(self, raw: pd.DataFrame, threshold: float, **_: Any) -> RunResult:
        with Tapestry() as inner:
            clean = CleanKnot(data=raw, _config=KnotConfig(id="clean"))
            score = ScoreKnot(data=clean, threshold=threshold, _config=KnotConfig(id="score"))
        return await self._run_inner(inner)
```

**Why:** Consistent with every other knot in pirn. All behaviour lives in `process()`. Pre-building the tapestry and passing it at construction creates a shared mutable object across runs, which is wrong. The fresh-per-call approach is the only correct one.

### 2.2 Inputs are wired as normal knot kwargs

```python
sub = ScorePipeline(
    raw=upstream_knot,     # Knot → parent, resolved by outer engine
    threshold=0.8,         # constant → config value
    _config=KnotConfig(id="score-pipeline"),
)
```

No `bind={}` dict. The kwarg names are the parameter names on `process()`. This is exactly how every other knot works. The outer engine resolves parent values before calling `process`, so inside `process` they arrive as plain values.

### 2.3 SubTapestry bypasses `Knot.__init__` (Map pattern)

`SubTapestry.__init__` sets `_mutable_*` attributes directly rather than calling `super().__init__()`. This is the established precedent set by `Map`. It allows SubTapestry to accept arbitrary named kwargs without the normal `process()` signature introspection constraint.

### 2.4 Output is implicit — `_run_inner` returns `RunResult`

`SubTapestry` provides a `_run_inner(tapestry)` helper that runs the inner tapestry and returns its `RunResult`. The user returns whatever they want from `process()` — typically the `RunResult`, or a value extracted from it. No `output=` parameter. Consistent with all other knots: `process()` returns a value, the engine wraps it in `Ok`.

### 2.5 Success/failure semantics

`_run_inner` raises `SubTapestryError` if the inner `RunResult.succeeded` is False. `Knot.__call__` catches it and wraps it as `Err`. The user can override this by catching the error in `process()` if they want different behaviour.

---

## 3. Nesting Structure — Model & Persistence

### 3.1 Nesting is a graph/model concern, not a lineage concern

`SubTapestry` holds a reference to the inner `Tapestry` it constructed at runtime. The structural relationship (which knot contains which tapestry) lives in the definition model, not in lineage records. Lineage tracks what happened during a run; nesting describes what the pipeline *is*.

### 3.2 Arbitrarily deep nesting is supported

A SubTapestry inside another SubTapestry works automatically because SubTapestry is just a Knot. Nesting depth is unbounded by design.

### 3.3 Persistence: materialized path

Hierarchical run records are stored using a **materialized path** on run records. Every run carries its full ancestry as a slash-delimited string.

```
run_id          run_path
─────────────── ──────────────────────────────────
outer-123       /outer-123
inner-456       /outer-123/inner-456
deep-789        /outer-123/inner-456/deep-789
```

**Query patterns:**
- All descendants of a root run: `WHERE run_path LIKE '/outer-123/%'` — one indexed prefix scan, any depth
- Direct children: `WHERE run_path LIKE '/outer-123/%' AND depth(run_path) = 2`
- Full ancestry: parse the path string
- Breadcrumb for viz: the path string itself, split on `/`

**Why materialized path over adjacency list:** adjacency list requires recursive CTEs for arbitrary depth traversal; CTEs do not index well and each level is a separate scan. Materialized path is a single indexed prefix query at any depth.

**Why materialized path over closure table:** closure table has faster reads for all-descendants queries at scale but requires N writes per run creation (one per ancestor). pirn's nesting depth is unlikely to make prefix scans a bottleneck, and the path string maps directly to viz breadcrumb navigation with no additional query. If traversal complexity grows to the point where a graph store is warranted, that is the migration path — not closure table.

### 3.4 Model changes required

**RunResult / run history records:**

| Field | Type | Description |
|-------|------|-------------|
| `run_path` | `str` | Materialized path including this run's own id. Root runs: `/{run_id}`. |
| `parent_knot_id` | `str \| None` | The SubTapestry knot id in the parent run that spawned this run. |

**SubTapestry knot in definition store:**

| Field | Type | Description |
|-------|------|-------------|
| `inner_tapestry_id` | `str \| None` | Tapestry id of the inner pipeline. Set after `_run_inner` executes. |

### 3.5 RunHistory new query method

```python
def children_of(self, run_id: str) -> list[RunResult]:
    """All direct child runs spawned by SubTapestry knots within run_id."""
```

Implemented as a prefix query on `run_path`.

---

## 4. Visualization

All three viz renderers need updates. The structural entry point is `isinstance(knot, SubTapestry)` — the renderer checks this to know a subgraph boundary exists and accesses `knot.inner_tapestry`.

### 4.1 Mermaid

SubTapestry node rendered as a Mermaid `subgraph` block containing its inner knots inline. The full nesting tree is visible in one diagram. No drill-down (static text output).

### 4.2 HTML (`html_for_tapestry`, `html_for_run`)

SubTapestry node rendered as a visually distinct grouped container with a dashed border. Clicking expands/collapses the inner graph in-place.

### 4.3 D3 Explorer

Full drill-down navigation:
- SubTapestry nodes are visually distinct (dashed border, indicator icon)
- Clicking a SubTapestry node transitions the graph view to the inner tapestry
- Breadcrumb trail at the top shows the nesting path (derived from `run_path` for run views, or tapestry ancestry for definition views)
- Back button / breadcrumb click navigates up one level
- Navigation state is a stack; arbitrary depth works automatically

---

## 5. Files Affected

| File | Change |
|------|--------|
| `pirn/nodes/sub_tapestry.py` | New — `SubTapestry` base class, `SubTapestryError` |
| `pirn/nodes/__init__.py` | Export `SubTapestry` |
| `pirn/core/run_result.py` | Add `run_path`, `parent_knot_id` fields |
| `pirn/backends/base/run_history.py` | Add `children_of(run_id)` to protocol |
| `pirn/backends/in_memory/in_memory_history.py` | Implement `children_of` |
| `pirn/backends/sqlite/sqlite_history.py` | Add `run_path` column, implement `children_of` |
| `pirn/viz/mermaid.py` | SubTapestry → `subgraph` block |
| `pirn/viz/html.py` | SubTapestry → grouped collapsible container |
| `pirn/viz/explorer.py` | Drill-down navigation, breadcrumb, navigation stack |
| `tests/nodes/test_sub_tapestry.py` | New — unit + integration tests |

---

## 6. Open Questions — Resolved

| Question | Decision |
|----------|----------|
| `process()` or no `process()`? | Has `process()` — user implements it |
| `bind={}` dict or kwargs? | Normal kwargs — consistent with all other knots |
| Explicit `output=` parameter? | No — output is implicit, whatever `process()` returns |
| Graph store for nesting? | No — materialized path in existing relational backends |
| Adjacency list vs closure table vs materialized path? | Materialized path |
| Lineage vs model for nesting structure? | Model — `run_path` on run records, not in `KnotLineage` |
