# ADR: SubTapestry Contract — process() Returns a Knot Value

Status: Accepted | Date: 2026-05-10

---

## Context

The original SubTapestry PRD described SubTapestry as a "knotless" knot — one that would accept a pre-built `Tapestry` instance at construction time and run it without a user-implemented `process()`. The ARD superseded this: SubTapestry has `process()`, and the user implements it. Inside `process()`, the user builds a fresh inner `Tapestry`, calls `self._run_inner(inner)`, and returns a value from the `RunResult`.

During the domain gap remediation audit, approximately 90 SubTapestry subclasses were found with a structural violation: `_run_inner()` was called but its return value was discarded or handled incorrectly. Some subclasses re-derived a domain value from the inner result in ways that bypassed the `SubTapestryError` propagation path defined in `SubTapestry.__call__`. Others stored the inner tapestry at `__init__` time, making them unsafe for concurrent execution.

---

## Decision

SubTapestry subclasses must conform to the following contract:

1. Implement `process(**kwargs)`.
2. Build a fresh inner `Tapestry` on each invocation — never reuse a pre-built instance stored at construction time.
3. Call `self._run_inner(inner)` and return a value derived from its `RunResult`.
4. Do not catch `SubTapestryError` inside `process()` unless the subclass deliberately wants to swallow inner failure.
5. Return a domain value or the `RunResult` itself — not `None`.

`_run_inner()` runs the inner tapestry, raises `SubTapestryError` if `run_result.succeeded` is `False`, and returns the `RunResult` on success. `Knot.__call__` catches `SubTapestryError` and wraps it as `Err` — no per-subclass error handling needed.

Nested run records use a materialized path on `run_path`:

```
run_id       run_path
──────────── ─────────────────────────
outer-123    /outer-123
inner-456    /outer-123/inner-456
deep-789     /outer-123/inner-456/deep-789
```

All descendants: `WHERE run_path LIKE '/outer-123/%'` — single indexed prefix scan at any depth.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| "Knotless" SubTapestry (original PRD) — pre-built tapestry at construction, no `process()` | Shared mutable object across runs is incorrect for concurrent execution. Fresh-per-call is the only correct approach. |
| SubTapestry stores the inner tapestry at `__init__` time, `process()` only calls `_run_inner` | Same problem — the tapestry is constructed once and potentially mutated by run bookkeeping across concurrent invocations. |
| Require subclasses to handle `SubTapestryError` themselves | Creates inconsistent error handling; every subclass would need boilerplate that `Knot.__call__` should own. |
| Adjacency list or closure table for nested run records | Adjacency list requires recursive CTEs for depth-N queries; closure table requires O(depth) inserts per run. Materialized path is a single indexed prefix scan at any depth with a single insert. |

---

## Consequences

**Positive:**
- All ~90 domain SubTapestry specializations conform to a single testable contract.
- Inner tapestry failure propagates to the outer `Err` result automatically — no per-subclass error handling needed.
- Fresh inner tapestry per call is safe for concurrent execution.
- `_run_inner` return value is always meaningful — callers cannot accidentally discard it.
- `WHERE run_path LIKE '/root/%'` retrieves all nested descendants in a single indexed scan.

**Negative:**
- All ~90 existing specialization SubTapestries across the seven domains required remediation — the bulk of Part IV of the domain gap remediation plan.
