# Features: Split Core and Domains

**Status:** Planning — 2026-06-09
**Tracking Issue:** [#51](https://github.com/snoodleboot-io/pirn/issues/51)
**Companion docs:** `PRD.md`, `ADR.md` (this directory)

---

## How to read this document

This is the **ordered, dependency-aware work breakdown** that turns the [ADR](./ADR.md) decisions into follow-up GitHub issues off #51. Items are grouped by ADR phase (0–5). Every item carries:

- **id** — stable handle (`SCD-NN`) used for cross-references and issue titles.
- **size** — S (≤ half day) / M (1–2 days) / L (3–5 days). No XL: anything larger is already split.
- **dependencies** — other ids that must merge first (hard, topological).
- **agent** — the executing agent (`devops-agent`, `refactor-agent`, `migration-agent`, `test-agent`, `document-agent`, `architect-agent`).
- **acceptance criteria** — testable "done" statements.

**Execution status:** Issue #51 is **planning only** (PRD + ADR + this file). **Every work item below is EXECUTION — deferred — and is NOT done in #51.** The single exception is `SCD-01` (the registry spike), which is the architectural gate that must clear before any extraction commits; it is still a *follow-up* issue, not part of #51's deliverables.

**Topological order (critical path):** core scaffold → connectors fold → residual-edge resolution → `data` → `ml` → compat/registry → publish. `signal`/`oilgas`/`agents`/`health` parallelize once their dependencies land.

> **DEFERRED (not this planning issue):** SCD-01 … SCD-29 — all are execution work tracked as follow-up issues. #51 ships only `PRD.md`, `ADR.md`, `FEATURES.md`.

---

## Feature: Phase 0 — Workspace Scaffold (no code moves)

Stand up the uv workspace, eight `pyproject.toml` skeletons, shared tool-config, and CI matrix skeleton **while all code still lives at `pirn/`**. Prove the tooling before any source moves. (ADR-1, ADR-7 Phase 0.)

### Story: The team can confirm `sweet_tea` multi-package registration works before committing to R1

#### SCD-01 — Spike **and resolve the 5 registry-key collisions**; verify `fill_registry(module=, library="pirn")` self-registration
- **size:** M (spike ≤ 1 day + collision resolution) · **type:** spike + refactor · **agent:** architect-agent → refactor-agent
- **dependencies:** none
- **Description:** Two-part architectural gate for ADR-4 (R1). **(a) Spike:** in a throwaway branch, copy one domain (e.g. `signal`) to a `src/`-layout `pirn_signal`, call `Registry.fill_registry(module=__name__, library="pirn")` from its `__init__`, confirm its knots register and resolve by bare name. **(b) RESOLVE the 5 confirmed key collisions** (B1 — verified: `register()` keys by `class_name.lower()`, bare-name lookup raises on >1 entry). This is NOT "document it" — R1 is non-viable until these are unique under `library="pirn"`. Apply the ADR-4 "Knot key collisions" table: **consolidate** `DatabaseConnectionPoolKnot` (delete the `data` duplicate, use core's), and **rename** the four genuine variants → `CdcMessageBrokerKnot`, `TableFreshnessCheck`, `EegBandpassFilter`, `EegNotchFilter` (update their YAML refs/tests). Two of the five (`databaseconnectionpoolknot`, `messagebrokerknot`) become core↔`pirn-data` cross-package collisions after the connectors fold, so resolution must precede SCD-05/06.
- **Acceptance Criteria:**
  - [ ] A `pirn_signal` `src/`-layout package registers its knots under `library="pirn"` when imported; bare-name YAML resolves via `AbstractInverterFactory[Knot].create(ref)` with `pirn` (core) NOT importing the domain.
  - [ ] A registry-uniqueness assertion (every `(library="pirn")` key maps to exactly one entry) passes across the whole knot set — i.e. all 5 collisions resolved.
  - [ ] `DatabaseConnectionPoolKnot` consolidated to a single core class; `CdcMessageBrokerKnot`, `TableFreshnessCheck`, `EegBandpassFilter`, `EegNotchFilter` renamed with all YAML/test references updated; full suite green.
  - [ ] Missing optional deps skip the affected module with a `SweetTeaWarning` (no hard raise), matching today's behaviour.
  - [ ] Decision note confirms or amends ADR-4 R1.

### Story: A developer can build and resolve the empty workspace locally and in CI

#### SCD-02 — Scaffold `[tool.uv.workspace]` root and eight `pyproject.toml` skeletons
- **size:** M · **type:** chore · **agent:** devops-agent
- **dependencies:** SCD-01
- **Description:** Create the workspace root `pyproject.toml` (`members = ["packages/*"]`, `[tool.uv.sources]` path wiring, `[dependency-groups] all`) and eight empty package skeletons under `packages/` per ADR-1, with **no source moved** — code stays at `pirn/`. Establishes the target layout so later phases only move files into a ready home.
- **Acceptance Criteria:**
  - [ ] Root `pyproject.toml` declares `[tool.uv.workspace]` members and `[tool.uv.sources]` workspace path deps for all eight packages.
  - [ ] Eight `packages/pirn-*/pyproject.toml` exist with name, version, `requires-python`, build-system (hatchling), and `[tool.hatch.build.targets.wheel] packages = ["src/<import_name>"]`.
  - [ ] `pirn-core` imports as `pirn`; each domain imports as `pirn_<domain>` (verified by the wheel packages key).
  - [ ] `uv lock` resolves the workspace and produces a single `uv.lock`.
  - [ ] Existing monolith at `pirn/` still builds and imports unchanged (no regression).

#### SCD-03 — Establish shared base tool-config (ruff/pyright/pytest) across the workspace
- **size:** M · **type:** chore · **agent:** devops-agent
- **dependencies:** SCD-02
- **Description:** Define a shared base ruff/pyright/pytest configuration that each package inherits, preventing the per-package config drift called out in PRD Risk #5. Centralize select rules, per-file-ignores, and pytest markers so all eight packages lint and type-check identically.
- **Acceptance Criteria:**
  - [ ] Ruff `select`/`per-file-ignores` (including `pirn/__init__.py` RUF022, viz E501, tests F841) are defined once and applied to all packages.
  - [ ] Pyright include/relaxations are expressed per package without duplicating rule bodies.
  - [ ] Pytest markers (perf, slow, mutation, heavy) and default `addopts` exclusions are consistent across packages.
  - [ ] Running ruff + pyright at the workspace root reports zero new violations vs. the current monolith baseline.

#### SCD-04 — Stand up the CI matrix skeleton for the workspace
- **size:** M · **type:** chore · **agent:** devops-agent
- **dependencies:** SCD-02, SCD-03
- **Description:** Add a CI workflow skeleton that resolves the workspace, runs lint/type/test against the (still monolithic) code, and is structured for a later per-package matrix (Python 3.11–3.14). No publish logic yet. De-risks CI before code moves.
- **Acceptance Criteria:**
  - [ ] CI installs the workspace via `uv sync` and runs lint, type-check, and the existing test suite green.
  - [ ] Matrix axes (package × Python version) exist as a skeleton even if currently fanning out to one package.
  - [ ] Change-detection scaffolding is present so later per-package gates can be added (PRD Risk #4).
  - [ ] Workflow runs on PR and `main` without altering current publish behaviour.

---

## Feature: Phase 1 — Fold Connectors into Core

Relocate `pirn/domains/connectors` into `pirn-core` as `pirn.connectors.*`; promote interfaces to core's public surface; keep all backend deps optional. (ADR-2, ADR-7 Phase 1.)

### Story: Connector interfaces become part of core's stable public API without adding hard deps

#### SCD-05 — Relocate connector interfaces into `pirn.connectors` and publish the public surface
- **size:** L · **type:** refactor · **agent:** refactor-agent
- **dependencies:** SCD-02
- **Description:** Move the connector **interface** types (`DatabaseConnectionPool`, `ObjectStore`, `MessageBroker`, `APIClient`, `FileFormat`, `ConnectionConfig`, `DsnScrubber`, `FileFormatRegistry`) into `packages/pirn-core/src/pirn/connectors/` and expose them at a stable `pirn.connectors.*` namespace per ADR-2 (open question #5: namespaced, not flattened). `PirnOpaqueValue`/`DataTransport`/`SerializerRegistry` stay on their existing `pirn.core.*` paths.
- **Acceptance Criteria:**
  - [ ] All connector interface types import from `pirn.connectors.*`.
  - [ ] `PirnOpaqueValue`, `DataTransport`, `SerializerRegistry` remain importable from their current `pirn.core.*` paths.
  - [ ] No interface module top-level-imports a backend dependency.
  - [ ] The 3 connector factory knots register under `library="pirn"` at core import time.

#### SCD-06 — Move connector backends + file-format codecs behind core optional extras
- **size:** L · **type:** refactor · **agent:** refactor-agent
- **dependencies:** SCD-05
- **Description:** Move the ~80 backend implementations (databases, object_storage, messaging, saas, bi_catalog, graph, timeseries, streaming, document, observability) and the ~90 file-format codecs into `pirn-core`, declaring every heavy dependency as an **optional extra** in `pirn-core`'s `pyproject.toml`. Phase per ADR-7 (interfaces first via SCD-05, then backends by category, then codecs in batches).
- **Acceptance Criteria:**
  - [ ] All connector/backend extras (`postgres`, `s3`, `kafka`, `zstd`, `snappy`, `lz4`, …) plus aggregates (`all-db`, `all-storage`, `all-stream`) are declared in `pirn-core`'s `pyproject.toml`.
  - [ ] Each backend imports its heavy deps lazily (method-level / `try-except` / `ExtrasLoader.require()`); none at module top level.
  - [ ] `numpy` serializer registration stays conditional (registered only if importable).
  - [ ] Installing `pirn-core` with no extras imports cleanly with zero backend packages present.

#### SCD-07 — Enforce constraint C2: core imports zero domains and no backend dep at import time
- **size:** S · **type:** chore · **agent:** devops-agent
- **dependencies:** SCD-05, SCD-06
- **Description:** Add an automated import-graph check (CI gate) asserting `pirn-core` imports no `pirn_*` domain package and that importing `pirn` triggers no backend third-party import. Operationalizes ADR-1 constraints C2 and the ADR-2 contract boundary.
- **Acceptance Criteria:**
  - [ ] CI fails if `src/pirn/` contains any `import pirn_<domain>`.
  - [ ] CI fails if importing `pirn` in a bare environment imports any backend package (asyncpg, aioboto3, kafka clients, zstandard, …).
  - [ ] Check runs on every PR and is wired into the required-checks set.

---

## Feature: Phase 2 — Resolve Residual Inter-Domain Edges

Relocate the two pure-abstract provider interfaces into core to break two edges; retain the one concrete-type edge as an explicit package dependency. Result: a tree rooted at core plus a single `ml→data` edge. (ADR-3, ADR-7 Phase 2.)

### Story: `agents` and `health` no longer require sibling domains for abstract provider interfaces

#### SCD-08 — Break `agents→ml`: move `EmbeddingProvider` to `pirn.core.providers`
- **size:** M · **type:** refactor · **agent:** refactor-agent
- **dependencies:** SCD-05
- **Description:** Relocate `EmbeddingProvider` (pure abstract, subclasses `PirnOpaqueValue`) from `pirn/domains/ml/embedding_provider.py` into `pirn.core.providers`, re-exported on core's public surface. Re-point ml's embedding implementations and the ~5 agents RAG files to import from core. Eliminates the `pirn-agents → pirn-ml` edge (ADR-3).
- **Acceptance Criteria:**
  - [ ] `EmbeddingProvider` lives in `pirn.core.providers` and is importable from core's public surface.
  - [ ] All agents RAG `document_processing` imports of `EmbeddingProvider` resolve from core, not ml.
  - [ ] ml's concrete embedding implementations subclass the core base; no behaviour change.
  - [ ] No remaining `agents → ml` import edge in the source tree.

#### SCD-09 — Break `health→agents`: move `LLMProvider` (+`Tool`) to `pirn.core.providers`
- **size:** M · **type:** refactor · **agent:** refactor-agent
- **dependencies:** SCD-05
- **Description:** Relocate `LLMProvider` (pure abstract async chat/stream interface, plus tightly-coupled `Tool`/`FunctionTool` if they travel with it) into `pirn.core.providers`. Re-point health's `clinical_nlp_extractor` and agents' concrete LLM providers to import from core. Eliminates the `pirn-health → pirn-agents` edge (ADR-3).
- **Acceptance Criteria:**
  - [ ] `LLMProvider` (and any co-relocated `Tool`/`FunctionTool`) lives in `pirn.core.providers`.
  - [ ] health's `clinical_nlp_extractor` imports `LLMProvider` from core.
  - [ ] agents' concrete LLM providers subclass the core base; no behaviour change.
  - [ ] No remaining `health → agents` import edge in the source tree.

#### SCD-10 — Confirm acyclic package DAG (constraints C1, C3)
- **size:** S · **type:** chore · **agent:** devops-agent
- **dependencies:** SCD-08, SCD-09
- **Description:** Add a topological-sort CI check over declared inter-package hard dependencies asserting the graph is acyclic (C1) and that exactly one domain→domain edge remains (`pirn-ml → pirn-data`, C3). New domain→domain edges fail the build pending an ADR amendment.
- **Acceptance Criteria:**
  - [ ] CI computes the package dependency graph and fails on any back-edge (cycle).
  - [ ] CI asserts the only domain→domain hard edge is `pirn-ml → pirn-data`.
  - [ ] The `ml→data` edge is retained as an explicit dependency (ADR-3), not broken.

---

## Feature: Phase 3 — Extract Domains (topological order)

Move each `pirn/domains/<x>` into `packages/pirn-<x>/src/pirn_<x>`, carrying its extras and a `fill_registry(module=__name__, library="pirn")` call. Order is strictly topological: `signal` → `oilgas` → `data` → `ml` → `agents` → `health`. Each is a separate mergeable PR. (ADR-1, ADR-4, ADR-7 Phase 3.)

> Each extraction item shares a common acceptance template: (a) source lands at `packages/pirn-<x>/src/pirn_<x>/`; (b) `__init__.py` calls `Registry.fill_registry(module=__name__, library="pirn")` under `SweetTeaWarning` suppression; (c) domain extras declared in the package `pyproject.toml`; (d) `ExtrasLoader` moves with the domain and its messages updated to `pirn_<x>`; (e) the package imports cleanly with no extras installed and raises a clean install-hint `ImportError` when a required extra is missing; (f) the in-repo import-rewrite codemod (SCD-17) updates references to this domain.

### Story: `signal` extracts first to de-risk the mechanics (standalone, no edges)

#### SCD-11 — Extract `pirn-signal` (standalone)
- **size:** L · **type:** refactor · **agent:** refactor-agent
- **dependencies:** SCD-04, SCD-10
- **Description:** Move `pirn/domains/signal` → `packages/pirn-signal/src/pirn_signal`. Standalone (no cross-domain edges), so it validates the extraction recipe before the coupled domains. Carries `signal` extras (`scipy`, `pywavelets`, `librosa`, `padasip`).
- **Acceptance Criteria:**
  - [ ] Common extraction template (a)–(f) satisfied.
  - [ ] `pirn-signal` depends only on `pirn-core` (no other domain).
  - [ ] Clean-env: `pip install pirn-signal` pulls `pirn-core` + scipy/pywavelets/librosa and nothing from data/ml/health/oilgas (install-isolation metric).
  - [ ] A bare-name signal-knot YAML resolves after `import pirn_signal`.

### Story: independent and leaf domains extract next

#### SCD-12 — Extract `pirn-oilgas` (→core)
- **size:** L · **type:** refactor · **agent:** refactor-agent
- **dependencies:** SCD-11
- **Description:** Move `pirn/domains/oilgas` → `packages/pirn-oilgas/src/pirn_oilgas`. Depends only on core. Carries `oilgas` extras (`segyio`, `lasio`, `resfo`).
- **Acceptance Criteria:**
  - [ ] Common extraction template (a)–(f) satisfied.
  - [ ] `pirn-oilgas` depends only on `pirn-core`.
  - [ ] Clean-env install isolation verified (no data/ml/health/signal pulled).

#### SCD-13 — Extract `pirn-data` (→core)
- **size:** L · **type:** refactor · **agent:** refactor-agent
- **dependencies:** SCD-11
- **Description:** Move `pirn/domains/data` → `packages/pirn-data/src/pirn_data` (largest domain, ~175 knots, 8 specializations). Depends only on core. Carries `data` + tier extras (`polars`, `datafusion`, `ibis`, `spark`, `ray-data`, `dask`, `modin`, `pathway`, `bytewax`), lakehouse (`delta`/`iceberg`/`hudi`), and `all-frames`/`all-lazy` aggregates. On the critical path (ml depends on it).
- **Acceptance Criteria:**
  - [ ] Common extraction template (a)–(f) satisfied.
  - [ ] All data tier/lakehouse extras and aggregates declared in `pirn-data`'s `pyproject.toml`.
  - [ ] `pirn-data` depends only on `pirn-core`; `DataBatch`/`LakehouseTable`/`FileSource`/`SqlSource` exported from `pirn_data`.
  - [ ] Clean-env install isolation verified.

#### SCD-14 — Extract `pirn-ml` (→core, →data)
- **size:** L · **type:** refactor · **agent:** refactor-agent
- **dependencies:** SCD-13, SCD-08
- **Description:** Move `pirn/domains/ml` → `packages/pirn-ml/src/pirn_ml`. **Declares the retained `pirn-data` hard dependency** (ADR-3) for `dataset_loader`'s use of `DataBatch`/`LakehouseTable`/`FileSource`/`SqlSource`. Carries `ml` extras (`numpy`, `pandas`, `scikit-learn`) plus optional `xgboost`/`lightgbm`/SHAP/`torch`/`tensorflow`.
- **Acceptance Criteria:**
  - [ ] Common extraction template (a)–(f) satisfied.
  - [ ] `pirn-ml` declares hard deps on `pirn-core` and `pirn-data`; `pip install pirn-ml` transitively installs `pirn-data`.
  - [ ] `dataset_loader` imports its data types from `pirn_data`; `EmbeddingProvider` from `pirn.core.providers` (SCD-08).
  - [ ] No `pirn_data → pirn_ml` edge exists (one-directional, acyclic).

#### SCD-15 — Extract `pirn-agents` (→core)
- **size:** L · **type:** refactor · **agent:** refactor-agent
- **dependencies:** SCD-08, SCD-13
- **Description:** Move `pirn/domains/agents` → `packages/pirn-agents/src/pirn_agents`. After SCD-08, agents depends only on core (no ml). No required heavy deps; provider/memory/tool deps are user-supplied or per-specialization extras.
- **Acceptance Criteria:**
  - [ ] Common extraction template (a)–(f) satisfied.
  - [ ] `pirn-agents` depends only on `pirn-core` (no `pirn-ml` edge).
  - [ ] RAG `document_processing` imports `EmbeddingProvider` from core.
  - [ ] Clean-env install isolation verified.

#### SCD-16 — Extract `pirn-health` (→core)
- **size:** L · **type:** refactor · **agent:** refactor-agent
- **dependencies:** SCD-09, SCD-15
- **Description:** Move `pirn/domains/health` → `packages/pirn-health/src/pirn_health`. After SCD-09, health depends only on core (no agents). Carries `health` extras (`pydicom`, `mne`, `nibabel`, `pyfaidx`, `pysam`, `fhir.resources`, `pyedflib`) and subset extras `mri`/`genomics`.
- **Acceptance Criteria:**
  - [ ] Common extraction template (a)–(f) satisfied.
  - [ ] `pirn-health` depends only on `pirn-core` (no `pirn-agents` edge).
  - [ ] `clinical_nlp_extractor` imports `LLMProvider` from core.
  - [ ] `mri` and `genomics` subset extras resolve independently of the full `health` extra.

---

## Feature: Phase 4 — Import Rewrite, Compatibility, Registry & Consumer Migration

Land the codemod across the repo, the `pirn.domains.*` compat shim, the registry self-registration ergonomics, and migrate tests/examples/docs/Docker. (ADR-4, ADR-5, ADR-7 Phase 4.)

### Story: All in-repo references migrate from `pirn.domains.<x>` to `pirn_<x>`

#### SCD-17 — Build and run the import-rewrite codemod across the repo
- **size:** M · **type:** chore · **agent:** migration-agent
- **dependencies:** SCD-02
- **Description:** Author a codemod (and publish it as the consumer-facing migration tool, SCD-23) that rewrites `import pirn.domains.<x>` / `from pirn.domains.<x> import …` → `pirn_<x>` across source, tests, examples, and docs. Run it incrementally as each domain extracts so the tree stays green. Updates stale docstrings/error strings referencing `pirn.domains.*` (ADR-4 adjacent fixes).
- **Acceptance Criteria:**
  - [ ] Codemod rewrites all six domain import forms deterministically and is idempotent.
  - [ ] After each domain extraction, no `pirn.domains.<that-domain>` references remain in source/tests/examples/docs (except the intentional compat shim).
  - [ ] Stale docstrings/error strings referencing `pirn.domains.*` are updated to `pirn_<x>`.
  - [ ] Codemod is runnable standalone (becomes the SCD-23 consumer tool).

### Story: Old `pirn.domains.<x>` call sites keep working for one deprecation cycle

#### SCD-18 — Ship the `pirn.domains.*` compatibility shim (Option B) in `pirn-core`
- **size:** M · **type:** feat · **agent:** code-agent
- **dependencies:** SCD-16
- **Description:** Add `pirn/domains/__init__.py` with lazy `__getattr__` (ADR-5) that, **only if** the corresponding `pirn_<x>` is installed, re-exports it and emits a `DeprecationWarning`; if absent, raises an `ImportError` pointing at `pip install pirn-<x>`. Deferred imports so core gains **no** hard domain dependency.
- **Acceptance Criteria:**
  - [ ] `import pirn.domains.data` succeeds (with `DeprecationWarning`) iff `pirn-data` is installed.
  - [ ] Accessing a domain whose package is absent raises `ImportError` naming the `pip install pirn-<x>` fix.
  - [ ] `pirn-core` declares no hard dependency on any domain package (verified by C2 / dependency-tree check).
  - [ ] Shim covers all six domains; warning text names the target `pirn_<x>` module.

### Story: Bare-name YAML resolves once domain packages are imported (registry parity)

#### SCD-19 — Add `discover_installed_domains()` helper and improve loader error
- **size:** M · **type:** feat · **agent:** code-agent
- **dependencies:** SCD-16
- **Description:** Add `pirn.discover_installed_domains()` (ADR-4) that introspects installed `pirn_*` distributions via `importlib.metadata` and imports them, restoring "import once, get everything" for opt-in users — a convenience, not the discovery mechanism. Improve the `yaml_loader` miss message to name the likely owning package.
- **Acceptance Criteria:**
  - [ ] `pirn.discover_installed_domains()` imports every installed `pirn_*` package, self-registering its knots under `library="pirn"`.
  - [ ] A cross-domain tapestry (data + ml + agents) resolves all knots by bare name after the helper runs (registry-parity metric).
  - [ ] An unresolved bare-name knot raises a message suggesting installing/importing the likely owning domain package.
  - [ ] `test_domains_extras.py` `sys.modules` manipulation rewritten to pop `pirn_<x>` keys.

### Story: Tests, examples, and docs build against the split packages

#### SCD-20 — Reorganize tests and centralize shared fixtures in `pirn-core`
- **size:** L · **type:** chore · **agent:** test-agent
- **dependencies:** SCD-16, SCD-17
- **Description:** Migrate the 160+ tests and ~9 conftests to the split layout; centralize cross-cutting fixtures in an importable `pirn-core` test-support module (ADR open question #6) so fixtures stay visible across separately-installed packages. Preserve assertions — the split is structural only.
- **Acceptance Criteria:**
  - [ ] All unit/integration/smoke/e2e tests pass against installed split packages (no behaviour change).
  - [ ] Shared fixtures import from a `pirn-core` test-support module; no fixture-visibility gaps across packages.
  - [ ] Per-package extras-isolation tests pass (each `pirn-<x>` imports without extras and raises a clean `ImportError` when a required dep is missing).
  - [ ] ~~`src/` layout forces tests to run against the installed package, not in-tree source.~~ **Superseded by [ADR Amendment A1](./ADR.md#amendment-a1--flat-layout--per-package-tests-2026-06-19-phase-5--scd-24):** flat layout + per-package `tests/`; the "import the installed package, not in-tree source" guarantee is now enforced by SCD-25 clean-env install-isolation instead of the directory layout. Shared fixtures live in the repo-root `conftest.py`.

#### SCD-21 — Migrate examples to per-package imports
- **size:** M · **type:** chore · **agent:** migration-agent
- **dependencies:** SCD-17
- **Description:** Run the codemod over the 11 example directories so scripts import `pirn_<x>` instead of `pirn.domains.<x>`, and update any READMEs/install hints to the new `pip install pirn-<x>` form.
- **Acceptance Criteria:**
  - [ ] All example scripts import `pirn_<x>` and run against installed split packages.
  - [ ] Example install instructions reference `pirn-<x>` distributions / extras.
  - [ ] No example references `pirn.domains.*` (except where intentionally demonstrating the deprecated shim).

#### SCD-22 — Update docs: `mkdocstrings.paths`, domain pages, and Docker dependency baking
- **size:** M · **type:** chore · **agent:** document-agent
- **dependencies:** SCD-16, SCD-17
- **Description:** Point `mkdocstrings.paths` at all eight packages so the unified `mkdocs` site builds; update domain/connectors doc pages and the consumer install/registration guidance (the "import the domain to register its knots" rule, ADR-4). Update `Dockerfile.ci`/`ci-heavy` to sync all workspace members so images carry the split packages.
- **Acceptance Criteria:**
  - [ ] `mkdocs build` succeeds with `mkdocstrings.paths` covering `pirn`, `pirn_signal`, `pirn_data`, `pirn_ml`, `pirn_agents`, `pirn_health`, `pirn_oilgas` (docs-build-unified metric).
  - [ ] Docs explain per-package install, the registry self-registration rule, and `discover_installed_domains()`.
  - [ ] Connectors public surface (`pirn.connectors.*`) is documented as part of core's API.
  - [ ] `Dockerfile.ci` and `ci-heavy` build with all workspace members synced; documented which image carries which packages.

### Story: External consumers have a documented, tooled migration path

#### SCD-23 — Publish the consumer migration guide + codemod and the `pirn[all-domains]` convenience
- **size:** S · **type:** document · **agent:** document-agent
- **dependencies:** SCD-17, SCD-18
- **Description:** Package the SCD-17 codemod as a consumer-runnable tool with a migration guide (`pirn.domains.<x>` → `pirn_<x>`) and a deprecation note. Document the optional `pirn[all-domains]` meta-extra (Option C) as an explicit, non-default convenience for users who want the monolith ergonomics (ADR-5).
- **Acceptance Criteria:**
  - [ ] Migration guide documents the codemod invocation and the `pirn.domains.<x>` → `pirn_<x>` mapping for all six domains.
  - [ ] Deprecation note states the window: shim for one minor, removal at the next major (1.0).
  - [ ] `pirn[all-domains]` meta-extra/meta-distribution is documented as opt-in (not the default install) and depends on all `pirn-*` packages.

---

## Feature: Phase 5 — CI/Coverage Rework, Versioning & Publish

Turn the CI skeleton into a per-package matrix with isolation/coverage gates, apply lockstep versioning, and publish N wheels. (ADR-1 constraints, ADR-6, ADR-7 Phase 5.)

### Story: CI enforces install isolation, layering, and per-package coverage across the matrix

#### SCD-24 — Build the per-package CI matrix with change-detection gates
- **size:** L · **type:** chore · **agent:** devops-agent
- **dependencies:** SCD-04, SCD-16
- **Description:** Expand the CI skeleton (SCD-04) into a per-package × Python (3.11–3.14) matrix with change-detection so only affected packages run on a PR, plus one unified cross-domain integration suite. Mitigates the ~192-job explosion (PRD Risk #4). **Change-detection is dependency-aware (closure):** a package runs when its own files change, an upstream `pirn-*` dependency changes (core → all; data → ml), or a shared-root file changes. Built on the **flat layout + per-package `tests/`** of [ADR Amendment A1](./ADR.md#amendment-a1--flat-layout--per-package-tests-2026-06-19-phase-5--scd-24); the unified suite selects the `cross_domain`-marked tests with all packages installed.
- **Acceptance Criteria:**
  - [x] Each package lints, type-checks, and tests on Python 3.11–3.14. *(per-package fan-out via `fromJSON`)*
  - [x] Change detection runs only the affected package(s) + the unified integration suite on a PR. *(dependency closure)*
  - [x] One cross-domain integration suite (data + ml + agents) runs the registry-parity check. *(`-m cross_domain`, 80 tests green)*
  - [ ] CI green across the full matrix on `main`. *(pending trigger re-enable at end of migration)*

#### SCD-25 — Add clean-env install-isolation and dependency-tree assertions per domain
- **size:** M · **type:** test · **agent:** test-agent
- **dependencies:** SCD-24
- **Description:** Add CI jobs that install each `pirn-<x>` into a clean environment and assert the resolved dependency tree contains only the expected packages (install-isolation success metric). Replaces the monolith's 50+ extras-isolation steps with per-package equivalents.
- **Acceptance Criteria:**
  - [ ] `pip install pirn-signal` in a clean env pulls `pirn-core` + scipy/pywavelets/librosa and nothing from data/ml/health/oilgas (asserted).
  - [ ] `pip install pirn-ml` pulls `pirn-data` transitively; other domains absent (asserted).
  - [ ] Per-domain extras-isolation imports pass (each extra installs and imports independently).
  - [ ] C2 (core→no domain) and the no-backend-dep-at-import check run in this job set.

#### SCD-26 — Rework coverage and mutation testing for the split packages
- **size:** M · **type:** test · **agent:** test-agent
- **dependencies:** SCD-24
- **Description:** Configure per-package coverage aggregation and update `mutmut` `paths-to-mutate` to each package's source tree (PRD Risk on mutation scope), preserving coverage-first thresholds across the workspace.
- **Acceptance Criteria:**
  - [ ] Coverage is computed per package and aggregated for the workspace report.
  - [ ] Coverage thresholds meet or exceed the current monolith baseline.
  - [ ] Mutation testing targets each package's source independently (PR-scoped changed-files + nightly full).
  - [ ] Codecov upload reflects per-package coverage.

### Story: All eight packages release in lockstep with a path to independent semver

#### SCD-27 — Implement lockstep version stamping across all packages
- **size:** M · **type:** chore · **agent:** devops-agent
- **dependencies:** SCD-16
- **Description:** Extend `calculate_version.py` to stamp the shared version onto all eight `pyproject.toml` files (lockstep, ADR-6), with domain packages pinning `pirn-core>=X,<X+1` and `pirn-ml` pinning `pirn-data>=X,<X+1` (constraint C4 version floor).
- **Acceptance Criteria:**
  - [ ] A single version bump stamps all eight packages identically (e.g. `0.4.0`).
  - [ ] Domain packages pin `pirn-core` lower/upper bounds; `pirn-ml` pins `pirn-data`.
  - [ ] C4 check passes: each `pirn-core` dependency pins `>=` the version introducing the symbols it uses.
  - [ ] The shim-removal major bump (1.0) is documented as a coordinated lockstep release.

#### SCD-28 — Build N wheels and publish/verify per package
- **size:** M · **type:** chore · **agent:** devops-agent
- **dependencies:** SCD-27
- **Description:** Convert the build job to produce one wheel per package, upload all as artifacts, and publish/verify each independently (testpypi on PR, pypi on `main`) per ADR-6.
- **Acceptance Criteria:**
  - [ ] Build produces eight wheels (`pirn-core`, `pirn-signal`, `pirn-data`, `pirn-ml`, `pirn-agents`, `pirn-health`, `pirn-oilgas`).
  - [ ] Each wheel publishes to testpypi on PR and pypi on `main`.
  - [ ] Verify jobs install each from the index and assert `import pirn` / `import pirn_<x>` and `tapestry-check --help`.
  - [ ] A cross-domain tapestry resolves knots by name after installing the relevant published packages (registry parity from PyPI).

#### SCD-29 — Document the post-1.0 independent-semver exit ramp and compatibility matrix
- **size:** S · **type:** document · **agent:** document-agent
- **dependencies:** SCD-27
- **Description:** Document the ADR-6 exit ramp: after 1.0, allow independent semver with a published compatibility floor (each domain's minimum `pirn-core`) and a maintained compatibility matrix.
- **Acceptance Criteria:**
  - [ ] Versioning policy doc states lockstep-through-migration → independent-semver-post-1.0.
  - [ ] A compatibility-matrix template (domain version × minimum `pirn-core`) is published.
  - [ ] Constraint C4 (version floor) is described as the enforcement mechanism.

---

## Delivery Sequence

**Phase 0 — Scaffold:** SCD-01 (gate) → SCD-02 → SCD-03 → SCD-04
**Phase 1 — Connectors fold:** SCD-05 → SCD-06 → SCD-07
**Phase 2 — Residual edges:** SCD-08, SCD-09 → SCD-10
**Phase 3 — Extraction (topological):** SCD-11 (signal) → SCD-12 (oilgas) ‖ SCD-13 (data) → SCD-14 (ml) ‖ SCD-15 (agents) → SCD-16 (health)
**Phase 4 — Rewrite/compat/registry:** SCD-17 (incremental) → SCD-18, SCD-19, SCD-20, SCD-21, SCD-22, SCD-23
**Phase 5 — CI/version/publish:** SCD-24 → SCD-25, SCD-26 ‖ SCD-27 → SCD-28 → SCD-29

**Critical path:** SCD-01 → SCD-02 → SCD-05 → SCD-06 → SCD-08 → SCD-13 (data) → SCD-14 (ml) → SCD-16 (health) → SCD-18/SCD-19 → SCD-24 → SCD-27 → SCD-28.

**Parallelizable within Phase 3:** `oilgas` (SCD-12), `agents` (SCD-15) extract in parallel with the `data→ml` spine once their dependencies (SCD-11; SCD-08+SCD-13) land. `signal` is first to de-risk the extraction recipe.

**EXECUTION boundary:** SCD-01 through SCD-29 are all **deferred execution work** (follow-up issues off #51). #51 itself delivers only `PRD.md`, `ADR.md`, and this `FEATURES.md`.

**Total:** 29 work items across 6 phases.

---

## Issue Tracking

Each SCD item has a follow-up GitHub issue off [#51](https://github.com/snoodleboot-io/pirn/issues/51) (label `split-core-domains`). Issues are **deferred execution work** — none are part of #51's planning deliverable.

| SCD | Issue | SCD | Issue | SCD | Issue |
|-----|-------|-----|-------|-----|-------|
| SCD-01 | [#52](https://github.com/snoodleboot-io/pirn/issues/52) | SCD-11 | [#62](https://github.com/snoodleboot-io/pirn/issues/62) | SCD-21 | [#72](https://github.com/snoodleboot-io/pirn/issues/72) |
| SCD-02 | [#53](https://github.com/snoodleboot-io/pirn/issues/53) | SCD-12 | [#63](https://github.com/snoodleboot-io/pirn/issues/63) | SCD-22 | [#73](https://github.com/snoodleboot-io/pirn/issues/73) |
| SCD-03 | [#54](https://github.com/snoodleboot-io/pirn/issues/54) | SCD-13 | [#64](https://github.com/snoodleboot-io/pirn/issues/64) | SCD-23 | [#74](https://github.com/snoodleboot-io/pirn/issues/74) |
| SCD-04 | [#55](https://github.com/snoodleboot-io/pirn/issues/55) | SCD-14 | [#65](https://github.com/snoodleboot-io/pirn/issues/65) | SCD-24 | [#75](https://github.com/snoodleboot-io/pirn/issues/75) |
| SCD-05 | [#56](https://github.com/snoodleboot-io/pirn/issues/56) | SCD-15 | [#66](https://github.com/snoodleboot-io/pirn/issues/66) | SCD-25 | [#76](https://github.com/snoodleboot-io/pirn/issues/76) |
| SCD-06 | [#57](https://github.com/snoodleboot-io/pirn/issues/57) | SCD-16 | [#67](https://github.com/snoodleboot-io/pirn/issues/67) | SCD-26 | [#77](https://github.com/snoodleboot-io/pirn/issues/77) |
| SCD-07 | [#58](https://github.com/snoodleboot-io/pirn/issues/58) | SCD-17 | [#68](https://github.com/snoodleboot-io/pirn/issues/68) | SCD-27 | [#78](https://github.com/snoodleboot-io/pirn/issues/78) |
| SCD-08 | [#59](https://github.com/snoodleboot-io/pirn/issues/59) | SCD-18 | [#69](https://github.com/snoodleboot-io/pirn/issues/69) | SCD-28 | [#79](https://github.com/snoodleboot-io/pirn/issues/79) |
| SCD-09 | [#60](https://github.com/snoodleboot-io/pirn/issues/60) | SCD-19 | [#70](https://github.com/snoodleboot-io/pirn/issues/70) | SCD-29 | [#80](https://github.com/snoodleboot-io/pirn/issues/80) |
| SCD-10 | [#61](https://github.com/snoodleboot-io/pirn/issues/61) | SCD-20 | [#71](https://github.com/snoodleboot-io/pirn/issues/71) | | |
