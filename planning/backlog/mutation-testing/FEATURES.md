# Features: Mutation Testing

**Status:** Backlog (partially done — see Feature 1)

---

## Feature: Mutation Testing Configuration (Done)

mutmut is installed, configured, and a baseline is established.

### Story: Developers can run mutation tests against the pirn source tree

#### Tasks (complete)
- Add `mutmut>=2.5,<4` to dev dependencies in `pyproject.toml`
- Configure `[tool.mutmut]` with `paths_to_mutate = "pirn/"`, `tests_dir = "tests/"`, and pytest runner
- Define `mutation` pytest marker in `[tool.pytest.ini_options]`
- Exclude `mutation` marker from default test run (`-m 'not slow and not mutation and not heavy'`)
- Establish baseline kill rate (initial run completed; per-module breakdown not yet documented)

---

## Feature: Module-Level Kill Rate Targets (Pending)

Scoped filter configuration and documented per-module thresholds that make mutation results actionable.

### Story: Developers can run mutmut against only the modules that matter for gating

#### Tasks
- Identify and list all pure-delegation files and abstract interface files to exclude from gating
- Add `paths_to_exclude` entries to `[tool.mutmut]` for excluded files
- Establish `pirn/core/` kill-rate baseline with exclusions applied; document result
- Establish `pirn/domains/data/specializations/` kill-rate baseline; document result
- Write `mutation-targets.md` in `docs/contributing/` specifying per-module thresholds and rationale

### Story: Developers know which surviving mutants are known noise vs real gaps

#### Tasks
- Run scoped mutmut on `pirn/core/` and triage all surviving mutants
- Classify each survivor: real gap (add test), known delegation noise (add to exclusion), or abstract interface (document as accepted)
- Write `mutmut-known-survivors.txt` baseline file listing accepted survivors with rationale

---

## Feature: CI Gate Integration (Pending)

Automated kill-rate enforcement on every PR for `pirn/core/`.

### Story: PRs that regress kill rate in `pirn/core/` fail CI

#### Tasks
- Add `mutation-ci` job to the CI workflow that runs mutmut scoped to `pirn/core/`
- Implement kill-rate threshold check: fail job if kill rate drops below the configured threshold
- Store threshold in `pyproject.toml` under `[tool.mutmut]` or a dedicated `[tool.pirn.mutation]` section
- Add a CI badge or PR comment reporting the current kill rate for `pirn/core/`

### Story: Developers can reproduce the CI mutation run locally

#### Tasks
- Document the exact mutmut invocation for `pirn/core/` in `docs/contributing/mutation-testing.md`
- Add a `make mutation-core` or `tox -e mutation-core` convenience target

---

## Feature: Nightly Scheduled Run (Pending)

Full-source mutation run that does not block PRs but provides visibility into regression trends.

### Story: Nightly CI runs mutmut against all of `pirn/` and reports results

#### Tasks
- Add `mutation-nightly` scheduled workflow (cron: daily, off-peak) scoped to full `pirn/`
- Configure the nightly run to emit a summary report (module-level kill rates as a table) to a CI artifact or notification channel
- Archive mutmut result database (`.mutmut-cache`) as a workflow artifact for trend comparison
- Implement kill-rate trend check: warn (not fail) if any module regresses by more than 5% week-over-week

### Story: The nightly run result is accessible without downloading a CI artifact

#### Tasks
- Post a kill-rate summary as a GitHub Actions job summary (markdown table per module)
- Add a `mutation-history/` directory to the repo for committed weekly snapshots (lightweight JSON: module → kill rate)
