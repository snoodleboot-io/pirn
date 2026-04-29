# Mutation testing plan

`pirn` ships `mutmut` configured in `pyproject.toml`, but mutation testing
is not yet a CI gate or part of the default test run. This document
records what we know, what an early scoped run surfaced, and what the
work to make it useful looks like.

## Configured baseline

`pyproject.toml` declares:

```toml
[tool.mutmut]
paths_to_mutate = "pirn/"
tests_dir = "tests/"
runner = ".venv/bin/python -m pytest tests/ -x -q --no-header"
```

The runner is pinned to the project venv's interpreter so `python -m
pytest` doesn't fall back to a system python that lacks the project's
dependencies.

## What an early scoped run showed

A targeted run against `pirn/core/result.py` (38 mutations) under
`tests/unit/` produced **19 killed / 19 survived = 50% kill rate**.

The survivors fell into four categories:

1. **Meaningless metadata mutations** — e.g., `TypeVar("T")` →
   `TypeVar("XXTXX")`. The string is debug-only metadata; no runtime
   path observes it. Mutmut can't tell.
2. **Error-message string mutations** — e.g., `f"unwrap() called on
   Err"` → `f"XXunwrap() called on ErrXX"`. The wording isn't asserted
   anywhere, and pinning specific wording in tests is brittle.
3. **`@dataclass(slots=True/False)` swaps** — *no longer applicable.*
   Phase 2 moved `Ok`/`Err`/`Skipped` from `@dataclass` to Pydantic
   `BaseModel`; the `slots` mutator no longer applies to these classes.
4. **Real test gaps** — e.g., the `frozen=True` → `frozen=False`
   mutation on `Err` and `Skipped` survived because we had a frozen
   test for `Ok` only. *Already addressed* in `tests/unit/test_result.py`
   (added `test_err_is_frozen`, `test_skipped_is_frozen`,
   `test_skipped_default_reason`, `test_skipped_default_detail_empty`,
   `test_ok_preserves_value_identity`).

## Why we haven't run it broadly yet

A full run against `pirn/` (~3,700 lines) at ~1.2 s per pytest
invocation would mean tens of minutes of wall time per pass. That's
fine for a scheduled job; it's too slow to gate every commit on. We
also need to address the noise categories above before a kill-rate
percentage is meaningful — without configuration, mutmut over-counts
trivially-survivable mutations and the score is misleadingly low.

## Plan

### 1. Configure mutator filters

Per-module disables for the mutator categories that produce noise on
this codebase:

- **Disable string-content mutations in error messages.** `mutmut` can
  be told to skip `f"..."` and `"..."` content mutations under a
  pattern. Concretely: skip mutations whose context is inside a `raise
  X(...)` call. Will be expressed as a `setup.cfg` `[mutmut]` block or
  via `mutmut`'s `pre_mutation` hook (it lets a Python function decide
  whether to apply each mutation).
- **Disable `TypeVar`-name and other metadata mutations** the same way.

### 2. Address known easy gaps first

For each module listed below, write the targeted tests that close
known low-hanging mutmut gaps before measuring. These are issues we
already know about from inspecting code — running mutmut to discover
them is overkill.

- `result.py` — done (frozen tests for all three variants, default
  reason and detail).
- `hashing.py` — assert hash format prefix (`sha256:`), assert hash
  length is `7 + 64`, assert distinct primitive types hash distinctly
  (`5` ≠ `5.0` ≠ `"5"` ≠ `True`).
- `config.py` — assert default values for every field (`validate_io`
  defaults `True`, `error_policy` defaults `SKIP_IF_PARENT_FAILED`,
  `tags` defaults `()`).
- `engine/shed.py` — assert `topological_order` returns a stable
  lexicographic-within-layer order, not just any topo order.
- `engine/engine.py` — assert lineage records carry the dispatcher
  name; assert `Ok` outcomes have `output_hash` set and `Err`/`Skipped`
  do not.

### 3. Set per-module kill-rate targets

Once filters are in place and easy gaps are closed:

| Module               | Target kill rate | Notes                                |
|----------------------|------------------|--------------------------------------|
| `core/result.py`     | ≥ 95%            | Tiny, well-defined, no IO.           |
| `core/hashing.py`    | ≥ 90%            | Pure function tree, lots of branches. |
| `core/config.py`     | ≥ 90%            | Pydantic validation; mutators are predictable. |
| `core/lineage.py`    | ≥ 85%            | Mostly Pydantic field declarations.  |
| `core/parameter.py`  | ≥ 80%            | Has small bypass paths around freeze. |
| `core/knot.py`       | ≥ 75%            | Constructor convention has many branches; some are validation-only. |
| `engine/shed.py`     | ≥ 85%            | Algorithmic; deterministic.          |
| `engine/engine.py`   | ≥ 70%            | Async wave loop with timing concerns; some branches genuinely hard to test. |
| `engine/dispatcher.py` | ≥ 80%          | Two small classes.                   |
| `managers/*.py`      | ≥ 90%            | Tiny, pure, lock-protected.          |
| `nodes/*.py`         | ≥ 75%            | Each node is small; recursion handled in `map_.py`. |
| `yaml_loader/*.py`   | ≥ 70%            | Heavy on parser branches.            |
| `tapestry.py`        | ≥ 80%            |                                      |

These are starting targets. We tighten them as the suite matures.

### 4. CI integration

Two-tier:

- **PR runs** — `mutmut run --use-coverage` against only changed files.
  Bounded: typically seconds to minutes per PR, not the full
  hour-plus run.
- **Scheduled (nightly or weekly)** — full `mutmut run` against
  `pirn/`, posting results to a `mutmut-baseline.json` checked into
  the repo. PRs that drop kill rate below the per-module target fail.

### 5. Custom mutators

Eventually, two `pirn`-specific mutators worth writing:

- **`ErrorPolicy` constant swap** — replace each occurrence of an
  `ErrorPolicy` constant with each other one and check our handling
  branches catch the substitution. Right now each `error_policy`
  branch has a corresponding integration test, but only by visual
  inspection.
- **Result-variant swap** — replace `return Ok(value=x)` with `return
  Err(record=...)` and vice versa to verify that downstream tests
  notice. This is an extreme version of "did we test this branch?"

## Running it locally

```bash
cd /path/to/pirn

# Full run — slow.  Allow tens of minutes.
.venv/bin/mutmut run

# Check what survived.
.venv/bin/mutmut results

# Inspect a specific surviving mutation.
.venv/bin/mutmut show <id>

# HTML report.
.venv/bin/mutmut html
```

The current `pyproject.toml` configuration runs the full test suite for
each mutation. If that's too slow, narrow `paths_to_mutate` to one
module and `tests_dir` / `runner` to the matching test file —
`pyproject.toml` can be temporarily edited or overridden via
`mutmut`'s CLI flags.
