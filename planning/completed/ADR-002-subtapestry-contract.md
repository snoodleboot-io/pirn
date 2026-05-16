# ADR-002: SubTapestry Contract — process() Returns a Knot Value

**Status:** Accepted
**Date:** 2026-05-10
**Branch:** feat/domain-gap-remediation-plan
**Source:** planning/archive/subtapestry-ard.md, planning/archive/subtapestry-prd.md

---

## Context

The original SubTapestry PRD described SubTapestry as a "knotless" knot — one that would
accept a pre-built `Tapestry` instance and run it without a user-implemented `process()`.

The ARD superseded this: SubTapestry has `process()`, and the user implements it. Inside
`process()`, the user builds and runs an inner `Tapestry`, then calls `self._run_inner(inner)`
and returns a value from it.

The problem discovered during the gap remediation audit was that approximately 90
SubTapestry subclasses across the domains had a structural correctness violation:
`_run_inner()` was being called inside `process()` but its return value was being
discarded or handled incorrectly. Specifically, many specialization SubTapestries called
`_run_inner()` and then re-derived a domain value from the inner result in ways that
bypassed the `SubTapestryError` propagation path defined in `SubTapestry.__call__`.

---

## Decision

SubTapestry subclasses must conform to the following contract:

1. Implement `process(**kwargs)`.
2. Build a fresh inner `Tapestry` on each invocation — never reuse a pre-built instance stored at construction time.
3. Call `self._run_inner(inner)` and return a value derived from its `RunResult`.
4. Do not catch `SubTapestryError` inside `process()` unless the subclass deliberately wants to swallow inner failure.
5. Return a domain value (extracted from the inner `RunResult`) or the `RunResult` itself — not `None`.

The `_run_inner()` helper:
- Runs the inner tapestry
- Raises `SubTapestryError` if `run_result.succeeded` is `False`
- Returns the `RunResult` on success

`Knot.__call__` catches `SubTapestryError` and wraps it as `Err`, so inner failure
propagates correctly to the outer pipeline without any boilerplate in `process()`.

Example conforming implementation:

```python
class ScorePipeline(SubTapestry):
    async def process(self, raw: pd.DataFrame, threshold: float, **_: Any) -> RunResult:
        with Tapestry() as inner:
            clean = CleanKnot(data=raw, _config=KnotConfig(id="clean"))
            score = ScoreKnot(data=clean, threshold=threshold, _config=KnotConfig(id="score"))
        return await self._run_inner(inner)
```

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| "Knotless" SubTapestry (original PRD) — pre-built tapestry passed at construction, no `process()` | Shared mutable object across runs is wrong. Fresh-per-call is the only correct approach for a framework with concurrent execution. |
| SubTapestry stores the inner tapestry at `__init__` time and `process()` just calls `_run_inner` | Same problem — the tapestry is constructed once and potentially mutated by run bookkeeping across concurrent invocations. |
| Require subclasses to handle `SubTapestryError` themselves | Creates inconsistent error handling; every subclass would need boilerplate that `Knot.__call__` should own. |

---

## Consequences

**Positive:**
- All ~90 domain SubTapestry specializations conform to a single testable contract.
- Inner tapestry failure propagates to the outer `Err` result automatically — no per-subclass error handling needed.
- Fresh inner tapestry per call is safe for concurrent execution.
- `_run_inner` return value is always meaningful — callers cannot accidentally discard it.

**Negative:**
- All ~90 existing specialization SubTapestries across the seven domains required
  remediation to conform to this contract. This was the bulk of Part IV of the gap
  remediation plan (completed 2026-05-10).

---

## Migration Notes

Part IV of the domain gap remediation plan (completed 2026-05-10) swept all SubTapestry
subclasses across all domains and corrected the `_run_inner()` usage pattern. The scope
was approximately 90 subclasses across:

- `pirn/domains/ml/specializations/` (~80 SubTapestry compositions)
- `pirn/domains/health/specializations/`
- `pirn/domains/signal/specializations/`
- `pirn/domains/oilgas/workflows.py`
- `pirn/domains/agents/specializations/`

Additionally, `LoopSubTapestry` (iterative agentic loops) was reviewed and conformed to
the SubTapestry contract as part of Part V (completed 2026-05-15). See commit
`56aff20` — "refactor(nodes): conform LoopSubTapestry to SubTapestry contract."

---

## Persistence: Materialized Path for Nested Runs

Run records for nested tapestries use a materialized path on `run_path`:

```
run_id          run_path
─────────────── ──────────────────────────────────
outer-123       /outer-123
inner-456       /outer-123/inner-456
deep-789        /outer-123/inner-456/deep-789
```

All descendants of a root run: `WHERE run_path LIKE '/outer-123/%'` — single indexed
prefix scan at any depth. Adjacency list and closure table were considered and rejected
(see subtapestry-ard.md section 3.3 for full rationale).
