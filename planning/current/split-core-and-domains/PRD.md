# PRD: Split Core and Domains

**Status:** Draft — Planning
**Created:** 2026-06-09
**Tracking Issue:** [#51](https://github.com/snoodleboot-io/pirn/issues/51) — *Refactor: split pirn into core + per-domain packages (uv workspace)*

---

## Problem

`pirn` ships today as a **single Hatch wheel** (`pirn` 0.3.0) that bundles core infrastructure together with all seven domain libraries under `pirn/domains/`. Every consumer — whether they need only signal processing or only agents — installs the same monolith and inherits the same optional-extras surface (`pirn[health]`, `pirn[signal]`, the 80+ connector extras, etc.).

This produces three concrete pains:

1. **No install-time isolation between domains.** A user who wants `pirn_signal` knots cannot install just that domain; they pull the whole `pirn` distribution and reason about extras that do not apply to them. Domain dependency trees (scipy vs. pydicom vs. scikit-learn vs. segyio) are coupled into one release.
2. **Layering is implicit, not enforced.** Core (`pirn/core`, `engine`, `nodes`, `backends`, `emitters`, `managers`, `streaming`, `triggers`, `viz`, `yaml_loader`, `exceptions`, `tapestry`, `replay`) imports **zero** domains, and domains form an acyclic DAG with `connectors` as a shared hub — but nothing at the package boundary guarantees this. Regressions that introduce a core→domain or a domain cycle are caught only by convention.
3. **Domains cannot version or release independently.** A bugfix to `data` knots forces a full `pirn` re-release. Domains mature at very different rates (data has 175 knots, oilgas 95), yet they are locked to one version string.

## Goal

Refactor the single `pirn` library into a **uv monorepo workspace** of independently installable packages: a **core** package (`pirn-core`, importable as `pirn`) plus **one package per domain**, where each domain package depends on `pirn-core`. The `connectors` hub is **folded into core** so domains depend on core rather than on a hub domain.

Consumers install only the domains they need (`pip install pirn-signal`, `pip install pirn-data`); layering is enforced by package boundaries; domains can version and release on their own cadence.

> **This PRD is planning-only.** It defines the target state, scope, and constraints. It does **not** move, rename, or refactor any source code. See [Out of Scope](#out-of-scope).

## Goals / Non-Goals

### Goals

- Define the **target package list** with distribution names and import names.
- Define the **per-package dependency mapping** — which optional-extras move to which package.
- Decide the packaging model, namespace strategy, and connectors placement (these are **agreed** — see below).
- Define a **public-API blast-radius strategy** for consumers whose code uses `import pirn.domains.<x>`.
- Define **high-level migration phasing** (detailed Feature → Story → Task breakdown lives in `FEATURES.md`).
- Define **success metrics** and capture **risks / open questions** for the architect (resolved in `ADR.md`).

### Non-Goals

- **Executing** any file move, rename, or refactor (tracked in follow-up issues from `FEATURES.md`).
- **Sub-splitting a domain** into multiple packages (e.g. `pirn_data.frames` as its own wheel). Each domain is one package.
- Changing **knot behaviour**, `process()` implementations, or the Knot/KnotConfig contracts.
- Redesigning the **CI/CD topology** beyond what the split structurally requires (the workspace CI design is an ADR concern, scoped in `FEATURES.md`).
- Adopting **entry-point-based** knot discovery as the primary mechanism — discovery stays Registry-reflection-based; entry points may be evaluated as a mitigation only.

## Agreed Decisions

These three decisions are **settled**. They are recorded here as PRD constraints; the architect will document rationale, alternatives, and consequences in `ADR.md`. Do not relitigate.

1. **Packaging model = uv monorepo workspace.** One git repo, multiple independently-installable packages (`pirn-core` + one per domain), wired via `[tool.uv.workspace]` members and `[tool.uv.sources]` path dependencies. Each package gets its own `pyproject.toml`.
2. **Namespace = distinct top-level packages.** Core stays importable as `pirn`. Each domain becomes its own top-level import package (`pirn_signal`, `pirn_data`, `pirn_ml`, `pirn_agents`, `pirn_health`, `pirn_oilgas`). This **breaks** existing `import pirn.domains.<x>` call sites — the import/public-API blast radius is **accepted** and is planned for in [Blast Radius](#publicapi-blast-radius).
3. **connectors is folded into core.** `connectors` is the shared hub (data→connectors 74, ml→connectors 30, etc.). After folding, domains depend on `pirn-core`, not on a hub domain. Connector interface types (`DatabaseConnectionPool`, `ObjectStore`, `MessageBroker`, `FileFormat`, `ConnectionConfig`) and the file-format codec ecosystem become part of `pirn-core`'s public surface.

## Target Package List

Eight packages total: one core + one per domain. `signal` is standalone; all other domains depend on `pirn-core`; three residual inter-domain edges (see [Residual Edges](#residual-inter-domain-edges)) are resolved before packaging.

| Distribution name | Import package | Source today | Depends on | Knots |
|-------------------|----------------|--------------|------------|-------|
| `pirn-core` | `pirn` | `pirn/` (core + engine + nodes + backends + emitters + managers + streaming + triggers + viz + yaml_loader + exceptions + tapestry + replay) **+ `pirn/domains/connectors` folded in** | `sweet_tea` | 8 + 3 (connector factory knots) |
| `pirn-signal` | `pirn_signal` | `pirn/domains/signal` | `pirn-core` | ~111 |
| `pirn-data` | `pirn_data` | `pirn/domains/data` | `pirn-core` | ~175 |
| `pirn-ml` | `pirn_ml` | `pirn/domains/ml` | `pirn-core`, **`pirn-data`** (declared edge, see below) | ~116 |
| `pirn-agents` | `pirn_agents` | `pirn/domains/agents` | `pirn-core` (edge to `ml` **broken** per ADR-3 — `EmbeddingProvider` moved to core) | ~136 |
| `pirn-health` | `pirn_health` | `pirn/domains/health` | `pirn-core` (edge to `agents` **broken** per ADR-3 — `LLMProvider`/`Tool` moved to core) | ~115 |
| `pirn-oilgas` | `pirn_oilgas` | `pirn/domains/oilgas` | `pirn-core` | ~95 |

Knot counts are approximate (Discovery reports a spread of 628–758 total depending on counting method); they are sizing signals, not contractual.

### Naming convention

- **Distribution** (what you `pip install`): hyphenated, `pirn-<domain>`.
- **Import** (what you `import`): underscored, `pirn_<domain>`.
- `pirn-core` is the one exception: it installs as `pirn-core` but **imports as `pirn`** to preserve the core public API (`from pirn import Knot, Tapestry, ...`).

## Per-Package Dependency Mapping

Every package gets its own `pyproject.toml` `[project.optional-dependencies]` section. The current monolithic extras are partitioned as follows.

| Package | Hard deps | Optional-extras moved into this package |
|---------|-----------|------------------------------------------|
| `pirn-core` | `cloudpickle>=3.0`, `numpy>=2.4.4`, `pydantic>=2.0`, `pyyaml>=6.0`, `sweet_tea>=0.2.46` (the current monolith hard deps — `numpy` is genuinely core, imported by `core/transport/serializers/numpy_serializer.py`) | **All connector/backend extras** (folded in): `sqlite`, `postgres`, `mysql`, `mssql`, `oracle`, `duckdb`, `bigquery`, `snowflake`, `redshift`, `clickhouse`, `databricks`; object storage (`s3`, `gcs`, `azure`, ...); messaging (`kafka`, `pubsub`, `kinesis`, `rabbitmq`, `valkey`, ...); file-format codecs (`zstd`, `snappy`, `lz4`, ...); SaaS/BI/observability connector extras; plus convenience aggregates (`all-db`, `all-storage`, `all-stream`). |
| `pirn-signal` | `pirn-core` | `signal` → `scipy`, `pywavelets`, `librosa` (+ `padasip` where used) |
| `pirn-data` | `pirn-core` | `data` → `pandas`, `pyarrow`; tier extras `polars`, `datafusion`, `ibis`, `spark`, `ray-data`, `dask`, `modin`, `pathway`, `bytewax`; lakehouse `delta`/`iceberg`/`hudi`; `all-frames`, `all-lazy` aggregates |
| `pirn-ml` | `pirn-core`, `pirn-data` | `ml` → `pandas`, `scikit-learn` (**`numpy` dropped — it arrives via `pirn-core`'s hard dep**) (+ optional `xgboost`, `lightgbm`, SHAP, heavy `torch`/`tensorflow` as separate extras) |
| `pirn-agents` | `pirn-core` | `agents` → (no required heavy deps; provider/memory/tool deps are user-supplied or per-specialization extras) |
| `pirn-health` | `pirn-core` | `health` → `pydicom`, `mne`, `nibabel`, `pyfaidx`, `pysam`, `fhir.resources`, `pyedflib`; subset extras `mri`, `genomics` |
| `pirn-oilgas` | `pirn-core` | `oilgas` → `segyio`, `lasio`, `resfo` |

A workspace-level convenience meta-extra (e.g. `pirn[all-domains]`) and the docs/dev extras must be reconstituted at the workspace root for CI and documentation builds.

**Extras consolidation rule.** Where two of today's extras land in the **same** package, fold the shared dependency into that package's base extra and keep a *separate* sub-extra only when it carries a genuinely heavy/niche stack:

- `scipy` (today in both `signal` and `emd`) → into **`pirn-signal`**'s base `signal` extra. Keep `emd` as a sub-extra only for the niche `EMD-signal` dependency.
- `nibabel` (today in both `health` and `mri`) → into **`pirn-health`**'s base `health` extra. Keep `mri` as a sub-extra for the heavy `SimpleITK`/`dipy` stack (not every health user needs it).
- `pandas` (in both `data` and `ml`) → **stays declared in each** package's extra (`pirn-data` and `pirn-ml`); they install in different combinations and pip/uv dedupe at install. No consolidation needed — cross-package, not same-package.
- `numpy` → **not declared in any domain extra**; it is a `pirn-core` hard dependency and reaches every domain transitively.

### Residual Inter-Domain Edges

Folding connectors into core resolves the `→connectors` edges (data, ml, agents, health, oilgas all become `→core`). It does **not** resolve three domain→domain edges that cross pure-Python symbols:

| Edge | Count | Symbols crossed | **Resolution (finalized in ADR-3)** |
|------|-------|-----------------|--------------------------------------|
| `ml → data` | ~5 | `DataBatch`, `LakehouseTable`, `FileSource`, `SqlSource` (in `dataset_loader`) | **Declare explicit dependency** `pirn-ml → pirn-data`. Concrete data types legitimately belong in `pirn-data`; not hoisted to core. |
| `agents → ml` | ~5 | `EmbeddingProvider` (RAG document_processing) | **BREAK the edge**: `EmbeddingProvider` is a pure abstract interface — relocated to `pirn-core` (`pirn.core.providers`). `pirn-agents` no longer depends on `pirn-ml`. |
| `health → agents` | ~1 | `LLMProvider`, `Tool` (clinical_nlp_extractor) | **BREAK the edge**: pure abstract interfaces — relocated to `pirn-core`. `pirn-health` no longer depends on `pirn-agents`. |

ADR-3 finalizes the two abstract-interface edges as **broken** (interfaces moved to core) and keeps `ml → data` as a **declared** dependency. The resulting package graph is a tree (every domain → core) plus the single acyclic `pirn-ml → pirn-data` edge. **The graph is acyclic; CI constraint C3 enforces this.**

## Public-API Blast Radius

The namespace change (decision #2) breaks every consumer line that reads `import pirn.domains.<x>` or `from pirn.domains.<x> import ...`. Discovery confirms the internal blast radius: 160+ tests, 11 example directories, docs, and the registry/YAML resolution path. **External** consumers are affected identically. Core's own public API (`from pirn import Knot, KnotConfig, Tapestry, knot, ...` — the 9–13 re-exported symbols) is **preserved** because `pirn-core` keeps the `pirn` import name.

Two sub-problems must be addressed; the architect selects per problem in the ADR.

### 1. Import-path migration (`pirn.domains.data` → `pirn_data`)

| Option | Description | Trade-off |
|--------|-------------|-----------|
| **A. Hard break + migration guide** | Remove `pirn.domains.*`; publish a codemod/`sed` migration guide and a version-gated deprecation note. | Cleanest end state; highest one-time consumer cost. |
| **B. Compatibility shim in `pirn-core`** | Ship a thin `pirn/domains/<x>.py` shim that re-exports from `pirn_<x>` with a `DeprecationWarning`, **only if** the domain package is installed. | Soft landing; keeps old call sites working for one or more releases. Cost: core must know domain names; shim deferred-imports to avoid hard dep. |
| **C. Transitional meta-package** | A `pirn` meta-distribution that depends on all `pirn-*` packages and re-exports `pirn.domains.*`, preserving the monolith install for laggards. | Maximum backward compatibility; risks defeating the isolation goal if it becomes the default install. |

**PRD recommendation:** **B for one deprecation cycle, then A.** Optionally publish **C** as an explicit `pirn[all-domains]` convenience for users who genuinely want everything. The architect finalizes the deprecation window.

### 2. Registry / YAML knot resolution

`pirn/__init__.py` calls `sweet_tea.Registry.fill_registry()` at import time, registering all domain knots under `library='pirn'`. YAML pipelines reference knots by bare name (e.g. `callable: object_store_read_source`), resolved via the global registry **before** dotted-path import. After the split, importing `pirn` (core only) discovers **zero** domain knots; each domain package must call `fill_registry()` from its own `__init__`. **Existing YAML breaks** unless the relevant domain package is imported before load.

| Option | Description | Trade-off |
|--------|-------------|-----------|
| **R1. Per-package self-registration, same library** | Each `pirn_<x>/__init__` calls `fill_registry()`, all registering under `library='pirn'`. Users `import pirn_data` (or install the extra) to populate the registry. | Existing bare-name YAML keeps working **once the domain is imported**. Requires documenting the "import the domain to register its knots" rule. |
| **R2. Per-package distinct library names** | Each domain registers under `library='pirn_<x>'`; YAML must qualify by library. | Avoids name collisions; **breaks** all existing bare-name YAML. |
| **R3. Fully-qualified dotted paths in YAML** | Drop registry resolution; require `callable: pirn_data.sources.object_store_read_source`. | Explicit and unambiguous; large YAML migration burden. |

**PRD recommendation:** **R1**, with a documented rule that installing/importing a domain package self-registers its knots under `library='pirn'`. The architect must **verify `sweet_tea` behaviour**: confirm `fill_registry()` scans the calling package (`__package__`) and that multiple packages registering under one library is supported without collision. This is an [open question](#open-questions-for-the-architect).

Adjacent fixes required regardless of option: `pirn/domains/extras_loader.py` error messages (`pirn.domains.<x> requires...` → `pirn_<x>`), stale docstrings/error strings referencing `pirn.domains.*`, and the `test_domains_extras.py` `sys.modules` manipulation.

## Migration Phasing (High Level)

Detailed Feature → Story → Task breakdown lives in `FEATURES.md`. At the PRD level the phasing is:

1. **Phase 0 — Workspace scaffold (no moves).** Stand up `[tool.uv.workspace]`, the eight `pyproject.toml` files, shared tool-config base (ruff/pyright/pytest), and CI matrix skeleton — while code still lives at `pirn/`. Validate the empty workspace builds.
2. **Phase 1 — Fold connectors into core.** Relocate `pirn/domains/connectors` into `pirn-core`; promote connector interfaces to core's public API; verify core still imports zero domains.
3. **Phase 2 — Resolve residual edges.** Apply the [edge decisions](#residual-inter-domain-edges) (relocate `EmbeddingProvider`/`LLMProvider` to core or declare explicit package deps). Confirm the package DAG is acyclic.
4. **Phase 3 — Extract domains.** One package per domain (`signal` first — standalone; then `data`; then `ml`, `oilgas`; then `agents`; then `health`, respecting dependency order). Each carries its own extras and `fill_registry()` call.
5. **Phase 4 — Compatibility & registry.** Land the chosen blast-radius option (shim/meta-package) and registry self-registration; migrate tests, examples, docs `mkdocstrings.paths`, and Docker image dependency baking.
6. **Phase 5 — Independent versioning & publish.** Per-package version strings, build matrix producing N wheels, publish/verify pipeline per package.

## Success Metrics

- **Install isolation:** `pip install pirn-signal` pulls `pirn-core` + scipy/pywavelets/librosa and **nothing** from data/ml/health/oilgas. Verified by a clean-env import + dependency-tree assertion in CI.
- **Layering enforced:** `pirn-core` imports zero `pirn_*` domain packages (automated import-graph check in CI fails the build on violation).
- **Acyclic package graph:** the resolved package dependency DAG has no cycles (automated check).
- **Registry parity:** a tapestry composed from ≥2 domains (e.g. data + ml + agents) resolves all knots by name after importing the respective packages — parity with today's monolithic behaviour.
- **Consumer migration path exists:** documented codemod/guide converts `pirn.domains.<x>` → `pirn_<x>`; the chosen compat shim keeps old call sites working (with `DeprecationWarning`) for the agreed window.
- **CI green across the matrix:** all eight packages lint, type-check, and test on the supported Python versions (3.11–3.14); extras-isolation tests pass per package.
- **Docs build unified:** `mkdocs` aggregates all eight packages' API references without a broken `mkdocstrings` path.
- **No behaviour change:** existing test assertions (post import-path migration) pass unchanged — the split is structural only.

## Risks

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| 1 | **YAML pipeline breakage** — bare-name knot references fail with "not found in registry" unless the domain package is imported before load. | **High** | Option R1 + document the import-to-register rule; verify `sweet_tea` multi-package registration under one library; provide a startup helper that imports installed domains. |
| 2 | **Import-time inter-domain dependency chains** — after ADR-3 the only retained inter-domain edge is `pirn-ml → pirn-data`; `import pirn_ml` imports `pirn_data` at module load and a missing package is a hard `ImportError`, not a soft skip. | Medium | `pirn-ml` declares `pirn-data` as a hard dependency (always installed together); `agents→ml` and `health→agents` are broken so those chains no longer exist. |
| 3 | **Connectors extraction/fold complexity** — 268 files, 80+ backends, 90 file-format codecs, 30+ external packages; promoting to core's public API enlarges core's contract. | **High** | Phase the fold: core interfaces first, then backends per category, then codecs in batches; enforce strict connectors interface boundaries so new backends don't leak transitive deps into core. |
| 4 | **CI matrix explosion** — 8 packages × extras × 4 Python × 6 suites could approach ~192 jobs. | Medium | Selective per-package gates on change detection; shared base tool-config to avoid drift; keep one unified integration suite for cross-domain composition. |
| 5 | **Tool-config / conftest fragmentation** — per-package ruff/pyright/pytest configs and 9 scattered conftests may drift or lose fixture visibility across separately-installed packages. | Medium | Shared base config pattern; centralize cross-cutting fixtures in `pirn-core` (or a test-support package); explicit fixture imports. |
| 6 | **Version skew** — independent semver lets `pirn-ml==0.4.0` depend on `pirn-core==0.3.0`, risking incompatible combinations. | Medium | Decide lockstep vs. independent semver (open question); publish a compatibility matrix; pin core lower-bounds in domain packages. |
| 7 | **Docker image bloat / build time** — `Dockerfile.ci` pre-bakes all extras; the workspace must sync all members at once. | Low–Med | Document which images carry which packages; keep `ci-heavy` (torch/tensorflow) separate from `ci-base`. |
| 8 | **Managers boundary** — `managers/` is imported by `SubTapestry` and `core.knot`; if it transitively touches a domain type, the fold creates a core→domain cycle. | Low | Verify the managers boundary before Phase 1; no such dependency is currently evident. |

## Open Questions for the Architect

1. ~~**Residual edges — break or declare?**~~ **RESOLVED in ADR-3:** break `agents→ml` and `health→agents` (interfaces moved to `pirn.core.providers`); declare `pirn-ml → pirn-data`.
2. **`sweet_tea` registry semantics — verify.** Does `fill_registry()` scan the calling package (`__package__`) so each domain self-registers correctly? ⚠️ **Registry key collisions are CONFIRMED, not hypothetical** (see Review B1): the registry key is `class_name.lower()`, multiple packages register under one `library="pirn"`, and a bare-name lookup with >1 entry **raises** (`AbstractInverterFactory[Knot].create(ref)` passes no `library`/`label`). Five real colliding keys exist today — `bandpassfilter`, `notchfilter`, `databaseconnectionpoolknot`, `messagebrokerknot`, `freshnesscheck` — so R1 alone does **not** make bare-name resolution unique. SCD-01 must *resolve* these (per-domain `library`, label disambiguation, or rename), not just document them.
3. **Blast-radius window.** Adopt compat shim (Option B) for how many releases before the hard break (Option A)? Ship the transitional meta-package (Option C) as `pirn[all-domains]` or not at all?
4. **Versioning policy.** Lockstep (all packages share one version, simplest compatibility) or independent semver (true per-domain release cadence, requires a compatibility matrix)?
5. **Connectors naming/identity.** Folded into core, is the public surface namespaced (`pirn.connectors.*`) or flattened into existing core modules? Confirm `PirnOpaqueValue`, `DataTransport`, and `SerializerRegistry` stay on stable core import paths for connector code.
6. **Cross-package test/conftest strategy.** Centralize shared fixtures in `pirn-core`, or introduce a dedicated `pirn-test-support` package?

## Out of Scope

This issue (#51) and these documents are **planning only**. Explicitly **not** in scope here:

- **Any source-code move, rename, or refactor** — no files relocate from `pirn/domains/` to `pirn_<x>/` in this issue.
- **Writing the new `pyproject.toml` files** or `[tool.uv.workspace]` wiring.
- **Modifying CI workflows, Dockerfiles, or `mkdocs.yml`.**
- **Migrating tests, examples, or YAML pipelines.**

All execution work is tracked as follow-up issues generated from `FEATURES.md`. The deliverables of #51 are this `PRD.md`, the architect's `ADR.md`, and `FEATURES.md`.
