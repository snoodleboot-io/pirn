# Backlog: Knot Kind / Visual Role Design for html_for_run

## Status
Deferred — tests skipped pending design resolution.

Skipped tests:
- `tests/integration/test_visualization.py::test_html_for_run_marks_sub_tapestry_node`
- `tests/integration/test_visualization.py::test_html_for_tapestry_marks_sub_tapestry_node`

## What Was Found

`html_for_run` was detecting sub-tapestry nodes by checking:

```python
"is_sub_tapestry": isinstance(result.outputs.get(rec.knot_id), RunResult)
```

This worked under the old `SubTapestry` contract where `process()` returned a `RunResult` as its output value. Under the new contract, `process()` returns a `Knot` (the sink), and the output value is the sink's resolved value (e.g. `6`). The check always returns `False` now, so `"sub-tapestry"` never appears in the HTML from `html_for_run`.

## Why It Was Not Just Patched

Several patch options were considered and rejected:

1. **`isinstance(output, RunResult)` check** — broken by contract change, was never a real design.
2. **`isinstance(knot, SubTapestry)` in viz** — `html_for_run` has no live `Knot` objects, only `RunResult` with `KnotLineage` records. Can't import and `isinstance`-check for locally-defined test subclasses.
3. **Magic string in `KnotLineage.extra`** — `extra` is an escape hatch, not a schema. Coupling SubTapestry identity to a magic dict key is spaghetti.
4. **`_lineage_extra()` hook on `Knot`** — SRP violation. `Knot` should not know about lineage serialization format.
5. **Engine importing `SubTapestry` to stamp a flag** — DIP violation. Core engine depending on a concrete node type.

## The Real Design Gap

`html_for_run` needs to know the *visual role* of each knot from a `KnotLineage` record alone, with no live objects. There is no clean mechanism for this today.

## What a Sound Design Looks Like

The right abstraction is a **knot kind** — a first-class typed property that flows from the `Knot` class definition through execution into the lineage record and out to the viz.

Candidate design:
- `Knot` base class declares `_knot_kind: ClassVar[str] = "knot"` (or an enum)
- `SubTapestry` overrides `_knot_kind = "sub_tapestry"`
- `KnotLineage` adds a proper `knot_kind: str` field (not in `extra`)
- Engine records `knot_kind=type(knot)._knot_kind` — generic, no concrete imports
- Viz maps `knot_kind` to CSS class / visual shape — generic, open/closed for new kinds

This satisfies SOLID:
- **SRP**: each class declares its own kind; engine records it; viz renders it
- **OCP**: new node types (e.g. `LoopSubTapestry`) add a `_knot_kind` override without touching engine or viz
- **DIP**: engine and viz depend on the `Knot` base contract, not concrete subclasses

## What Needs to Happen

1. Design review: decide on `str` vs enum for `knot_kind`; agree on the set of kinds
2. Add `knot_kind` field to `KnotLineage` — assess migration impact on existing history backends
3. Add `_knot_kind` classvar to `Knot` base and all relevant subclasses
4. Update engine to record it generically
5. Update `html_for_run` to use `rec.knot_kind` instead of output inspection
6. Remove `pytest.mark.skip` from the two visualization tests above
