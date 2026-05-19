# PRD: SubTapestry Contract

Status: Complete | Completed: 2026-05-10 (LoopSubTapestry: 2026-05-15)

---

## Problem

Approximately 90 SubTapestry subclasses across the seven domains had a structural correctness violation: `_run_inner()` was called inside `process()` but its return value was discarded or handled incorrectly. Many specialization SubTapestries called `_run_inner()` and then re-derived a domain value from the inner result in ways that bypassed the `SubTapestryError` propagation path defined in `SubTapestry.__call__`.

Additionally, the original PRD described SubTapestry as a "knotless" knot — one that would accept a pre-built `Tapestry` instance at construction time and run it without a user-implemented `process()`. The ARD superseded this design, but many subclasses were written against the old mental model: they stored the inner tapestry at `__init__` time rather than building a fresh one per call, making them unsafe for concurrent execution.

---

## Goal

Establish one correct SubTapestry contract, enforce it across all ~90 subclasses, and ensure that inner tapestry failure propagates automatically to the outer `Err` result without per-subclass boilerplate.

---

## Success Criteria (all met)

- Contract codified: `process()` builds a fresh inner `Tapestry` per call, calls `self._run_inner(inner)`, and returns a value derived from the `RunResult`.
- `SubTapestryError` propagation is owned by `Knot.__call__` — subclasses do not catch it unless deliberately swallowing failure.
- All ~90 SubTapestry subclasses across ml, health, signal, oilgas, and agents domains remediated.
- `LoopSubTapestry` conforms to the same contract.
- Nested run records stored using a materialized path on `run_path` — supports `WHERE run_path LIKE '/outer-id/%'` prefix scans at any depth.

---

## Scope

### In scope

- Contract definition and documentation in `SubTapestry` docstring and `sub_tapestry.py`
- Remediation of all ~90 domain SubTapestry subclasses:
  - `pirn/domains/ml/specializations/` (~80 SubTapestry compositions)
  - `pirn/domains/health/specializations/`
  - `pirn/domains/signal/specializations/`
  - `pirn/domains/oilgas/workflows.py`
  - `pirn/domains/agents/specializations/`
- `LoopSubTapestry` conformance review and fix
- RunHistory nesting support via materialized path on `run_path`

### Out of scope

- SubTapestry `@subtapestry` decorator (deferred — users subclass directly)
- Changing `_run_inner` signature or return type
