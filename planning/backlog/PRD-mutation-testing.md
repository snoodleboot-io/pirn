# PRD: Mutation Testing CI Integration

**Status:** Backlog (mutmut configured; CI gate not yet wired)
**Priority:** Medium

---

## Problem Statement

`pirn` ships `mutmut` configured in `pyproject.toml`, but mutation testing is not a CI gate and is not part of the default test run. Kill rate is unmeasured at the module level, meaning test suite quality is unknown beyond line coverage. A 50% kill rate on `core/result.py` in an early scoped run revealed real gaps (subsequently fixed) and identified noise categories that require filtering before broader measurement is meaningful.

Without a CI gate, kill rate can silently degrade as new code is added.

---

## What's Done

- `mutmut` declared in `pyproject.toml` with `paths_to_mutate`, `tests_dir`, and `runner` configured
- Runner pinned to `.venv/bin/python` to avoid system-python fallback
- Early scoped run against `core/result.py`: 19 killed / 19 survived (50% kill rate)
- Four survivor categories identified:
  - Meaningless metadata mutations (`TypeVar` name strings)
  - Error-message string mutations (wording not asserted; asserting wording is brittle)
  - `@dataclass(slots=...)` swaps — no longer applicable (classes migrated to Pydantic `BaseModel`)
  - Real test gaps — frozen-model tests for `Err` and `Skipped` (now addressed in `tests/unit/test_result.py`)
- Known module-level gaps identified in: `hashing.py`, `config.py`, `engine/shed.py`, `engine/engine.py`

---

## What Remains

### 1. Configure mutator filters

Suppress noise categories before measuring kill rate broadly:

- **Error-message string mutations** — configure `pre_mutation` hook to skip mutations whose context is inside a `raise X(...)` call
- **TypeVar name and other metadata mutations** — configure the same hook to skip `TypeVar(...)` string argument mutations
- Express filters in `setup.cfg` `[mutmut]` block or via the `pre_mutation` Python hook

### 2. Close known easy gaps

Write targeted tests for modules with known low-hanging gaps before running mutmut to measure them:

| Module | Gaps to close |
|--------|--------------|
| `core/hashing.py` | Assert hash format prefix (`sha256:`), assert hash length is `7 + 64`, assert distinct primitive types hash distinctly (`5` ≠ `5.0` ≠ `"5"` ≠ `True`) |
| `core/config.py` | Assert default values for every field (`validate_io` defaults `True`, `error_policy` defaults `SKIP_IF_PARENT_FAILED`, `tags` defaults `()`) |
| `engine/shed.py` | Assert `topological_order` returns stable lexicographic-within-layer order, not just any valid topo order |
| `engine/engine.py` | Assert lineage records carry the dispatcher name; assert `Ok` outcomes have `output_hash` set and `Err`/`Skipped` do not |

### 3. Establish per-module kill-rate targets

Once filters are in place and easy gaps are closed, run scoped mutmut per module and establish baselines:

| Module | Target kill rate | Notes |
|--------|-----------------|-------|
| `core/result.py` | ≥ 95% | Tiny, well-defined, no IO |
| `core/hashing.py` | ≥ 90% | Pure function tree, many branches |
| `core/config.py` | ≥ 90% | Pydantic validation; mutators are predictable |
| `core/lineage.py` | ≥ 85% | Mostly Pydantic field declarations |
| `core/parameter.py` | ≥ 80% | Small bypass paths around freeze |
| `core/knot.py` | ≥ 75% | Constructor convention has many branches; some are validation-only |
| `engine/shed.py` | ≥ 85% | Algorithmic; deterministic |
| `engine/engine.py` | ≥ 70% | Async wave loop with timing concerns; some branches genuinely hard to test |
| `engine/dispatcher.py` | ≥ 80% | Two small classes |
| `managers/*.py` | ≥ 90% | Tiny, pure, lock-protected |
| `nodes/*.py` | ≥ 75% | Each node is small; recursion handled in `map_.py` |
| `yaml_loader/*.py` | ≥ 70% | Heavy on parser branches |
| `tapestry.py` | ≥ 80% | |

Check these targets into `mutmut-baseline.json` at the repo root after first full run.

### 4. Wire CI integration

Two-tier CI setup:

- **PR runs** — `mutmut run --use-coverage` scoped to changed files only. Bounded runtime: typically seconds to minutes per PR. Fails the PR if any changed module drops below its per-module target in `mutmut-baseline.json`.
- **Scheduled (nightly or weekly)** — full `mutmut run` against `pirn/`. Posts results to `mutmut-baseline.json`. PRs that drop kill rate below target on the next PR run are blocked.

CI configuration lives in `.github/workflows/` (or equivalent CI provider config). The scheduled run needs a separate workflow job with a longer timeout.

### 5. Custom pirn-specific mutators (future)

Two mutators worth writing once the CI gate is stable:

- **`ErrorPolicy` constant swap** — replace each `ErrorPolicy` constant with each other to verify handling branches catch the substitution
- **Result-variant swap** — replace `return Ok(value=x)` with `return Err(record=...)` and verify downstream tests notice

These are lower priority than getting the CI gate working.

---

## Success Criteria

1. `pre_mutation` hook suppresses error-message string mutations and `TypeVar` metadata mutations
2. All modules in the target table have been run through `mutmut` and have a recorded baseline in `mutmut-baseline.json`
3. PR CI job runs `mutmut --use-coverage` against changed files and fails the PR if kill rate drops below target
4. Scheduled CI job runs full `mutmut` and updates `mutmut-baseline.json`
5. Known easy gaps in `hashing.py`, `config.py`, `shed.py`, `engine.py` are closed with targeted unit tests
6. `mutmut-baseline.json` is checked into the repo and updated by the CI job via automated PR or direct commit to main
