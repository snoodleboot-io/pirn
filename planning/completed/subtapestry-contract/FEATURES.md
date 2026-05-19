# Features: SubTapestry Contract

---

## Feature: SubTapestry Contract Definition

Define the single correct contract for SubTapestry subclasses and enforce it in the framework's `_run_inner` helper and `Knot.__call__` error propagation path.

### Story: Framework users can implement SubTapestry correctly by following the docstring contract

As a framework user, I can read `SubTapestry`'s docstring and understand exactly how to implement `process()` — build a fresh tapestry, call `_run_inner`, return a derived value — so that inner failures propagate automatically without boilerplate.

#### Tasks

- Update `pirn/nodes/sub_tapestry.py` — codify the five-point contract in the `SubTapestry` class docstring
- Verify `SubTapestry._run_inner()` raises `SubTapestryError` when `run_result.succeeded` is `False`
- Verify `SubTapestry.__call__` catches `SubTapestryError` and wraps it as `Err`
- Add `SubTapestryError` to `pirn/nodes/__init__.py` exports

---

## Feature: Domain Subclass Remediation (~90 files)

Sweep all SubTapestry subclasses across the seven domains and correct the `_run_inner()` usage pattern — discard the pre-built tapestry stored at `__init__`, build fresh per call, and return the derived value from `RunResult`.

### Story: All ml domain SubTapestry specializations conform to the contract

As a pipeline operator, I can trust that ml domain compositions (training pipelines, evaluation workflows, feature engineering workflows) will propagate inner failure to the outer `Err` result without silent swallowing.

#### Tasks

- Remediate all SubTapestry subclasses in `pirn/domains/ml/specializations/` (~80 files): replace pre-built tapestry patterns with fresh-per-call builds; ensure `_run_inner` return value is used; remove incorrect domain-value re-derivation that bypassed `SubTapestryError`

### Story: All health, signal, oilgas, and agents domain SubTapestry specializations conform to the contract

As a pipeline operator, I can trust that health, signal, oilgas, and agents domain compositions propagate inner failure correctly.

#### Tasks

- Remediate all SubTapestry subclasses in `pirn/domains/health/specializations/`
- Remediate all SubTapestry subclasses in `pirn/domains/signal/specializations/`
- Remediate all SubTapestry subclasses in `pirn/domains/oilgas/workflows.py`
- Remediate all SubTapestry subclasses in `pirn/domains/agents/specializations/`

---

## Feature: LoopSubTapestry Contract Conformance

`LoopSubTapestry` implements iterative agentic loops. Its internal loop structure was reviewed and conformed to the same SubTapestry contract — fresh inner tapestry per iteration, `_run_inner` return value used correctly.

### Story: LoopSubTapestry users get consistent inner-failure propagation across loop iterations

As an agentic pipeline author, I can use `LoopSubTapestry` knowing that if any inner loop iteration fails, the failure propagates as `SubTapestryError` and is caught by `Knot.__call__` — no iteration result is silently lost.

#### Tasks

- Audit `pirn/nodes/loop_sub_tapestry.py` against the five-point SubTapestry contract
- Refactor `LoopSubTapestry` to build a fresh inner tapestry per loop iteration rather than reusing a stored instance
- Add `docs/contributing/agentic-loops.md` — guide explaining `LoopSubTapestry` semantics and correct implementation pattern

---

## Feature: RunHistory Nesting Support

Store nested run records using a materialized path on `run_path` so that all descendants of any root run can be retrieved in a single indexed prefix scan.

### Story: Platform operators can retrieve all nested run records for a root run without recursive queries

As a platform operator, I can query `WHERE run_path LIKE '/outer-id/%'` to retrieve all inner and deep-nested run records for any root run — no recursive CTEs or closure table joins required.

#### Tasks

- Update run record persistence to write `run_path` as a materialized path string on every inner run (`/outer-id/inner-id`)
- Ensure the `run_path` column is indexed
- Update `RunHistory` query helpers to support prefix-scan retrieval of all descendants
