# PRD: Mutation Testing

**Status:** Backlog
**Initiative:** mutation-testing

---

## Problem

pirn has a large test suite, but test coverage percentage alone does not indicate test quality. A test that exercises a branch without asserting the output provides false confidence. Mutation testing addresses this by injecting small code changes (mutants) and checking whether any test fails — a surviving mutant indicates a test gap.

`mutmut` is configured in `pyproject.toml` and a baseline kill rate has been established. However, running mutmut unfiltered against the full `pirn/` source tree produces excessive noise:

- **False survivors in pure-delegation code:** Many knot methods delegate entirely to library calls (scipy, polars, sklearn). Mutation of a keyword argument may not be caught by a unit test but would be caught immediately in integration. These survivors inflate the noise count without indicating real gaps.
- **No per-module kill-rate targets:** Without module-level thresholds, there is no way to know whether the core (`pirn/core/`) is well-tested relative to a less-critical domain file.
- **No CI gate:** Mutation tests are excluded from the default pytest run (`-m 'not slow and not mutation and not heavy'`). There is no enforcement mechanism. Kill rate can regress silently.
- **Runtime:** A full unfiltered run against `pirn/` (~1,246 Python files) takes several hours. Without a scoping strategy, mutation testing is impractical to run in CI.

## What Is Already Done

- `mutmut>=2.5,<4` is a declared dev dependency
- `[tool.mutmut]` is configured in `pyproject.toml`: `paths_to_mutate = "pirn/"`, `tests_dir = "tests/"`, `runner = ".venv/bin/python -m pytest tests/ -x -q --no-header"`
- The `mutation` pytest marker is defined; mutation-specific assertions can be gated behind it
- A baseline kill rate exists (not yet documented per module)

## Goal

Make mutation testing actionable: filter out noise, establish per-module kill-rate targets, add a CI gate for core modules, and schedule nightly full runs.

## Success Criteria

- mutmut filter config excludes pure-delegation files and library-call-only paths from gating
- Per-module kill-rate targets are documented and enforced for `pirn/core/` (target: ≥85%) and `pirn/domains/data/` (target: ≥75%)
- CI gate runs mutmut on `pirn/core/` on every PR; fails if kill rate drops below threshold
- Nightly scheduled run covers full `pirn/` and posts a summary; does not block PRs
- Decision on mutmut vs cosmic-ray is made and documented in the ADR

## Out of Scope

- Achieving specific kill rates in domain libraries other than data (future sprint)
- Mutation testing of test files themselves
