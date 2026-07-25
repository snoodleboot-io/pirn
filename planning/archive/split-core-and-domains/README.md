# Split Core and Domains — Planning Package

**Status:** Planning — Draft
**Date:** 2026-06-09
**Tracking Issue:** [#51](https://github.com/snoodleboot-io/pirn/issues/51) — *Refactor: split pirn into core + per-domain packages (uv workspace)*

> **PLANNING ONLY (issue #51). EXECUTION IS DEFERRED.** This package ships documents only. **No source code is moved, renamed, or refactored by #51.** Every work item (SCD-01 … SCD-29) in `FEATURES.md` is a follow-up issue off #51; #51 itself delivers only the documents indexed below.

---

## Problem

`pirn` ships today as a **single Hatch wheel** (`pirn` 0.3.0, `packages=["pirn"]`) that bundles core infrastructure together with all seven domain libraries under `pirn/domains/`. Every consumer installs the whole monolith and inherits the entire optional-extras surface (scipy + pydicom + scikit-learn + segyio + 80+ connector extras) regardless of which domain they actually use. This produces three concrete pains: **no install-time isolation** between domains (you cannot install just `signal`); **layering is implicit, not enforced** (core imports zero domains and domains form an acyclic DAG today, but only by convention); and **domains cannot version or release independently** (a `data` bugfix forces a full `pirn` re-release). The fix is to restructure into a **uv monorepo workspace** of independently-installable packages: a `pirn-core` package (still importable as `pirn`) plus one package per domain, each depending on `pirn-core`.

## Agreed Decisions (settled — design around these, do not relitigate)

1. **Packaging model = uv monorepo workspace.** One git repo, multiple independently-installable packages (`pirn-core` + one per domain), wired via `[tool.uv.workspace]` members and `[tool.uv.sources]` path deps. Each package gets its own `pyproject.toml`. `src/` layout is mandatory (forces tests to run against the installed wheel, which is how install-isolation is verified).
2. **Namespace = distinct top-level packages.** Core stays importable as `pirn`; each domain becomes its own top-level import package (`pirn_signal`, `pirn_data`, `pirn_ml`, `pirn_agents`, `pirn_health`, `pirn_oilgas`). This **breaks** existing `import pirn.domains.<x>` call sites — the blast radius is **accepted** and planned for (`IMPORT_MIGRATION.md`).
3. **connectors is folded into core.** It is the shared hub (data→connectors 74, ml→connectors 30, …). After folding, domains depend on `pirn-core`, not on a hub domain. Connector interfaces (`DatabaseConnectionPool`, `ObjectStore`, `MessageBroker`, `FileFormat`, `ConnectionConfig`, …) become part of core's public surface at `pirn.connectors.*`; all backend deps stay optional.
4. **Residual edges resolved (ADR-3):** `agents→ml` and `health→agents` are **broken** by relocating the pure-abstract interfaces `EmbeddingProvider` and `LLMProvider` into `pirn.core.providers`. The one concrete-type edge `ml→data` (`DataBatch`/`LakehouseTable`/`FileSource`/`SqlSource` in `dataset_loader`) is **retained as an explicit `pirn-ml → pirn-data` package dependency**. Final graph: every domain → core, plus a single `pirn-ml → pirn-data` edge. Must remain acyclic.

## Target Package List

Eight packages: one core + one per domain. Distribution names are hyphenated (`pip install`), import names are underscored (`import`). `pirn-core` is the exception — installs as `pirn-core`, imports as `pirn`.

| Distribution | Import name | Contents (source today) | Depends on | ~Knots |
|--------------|-------------|--------------------------|------------|-------:|
| `pirn-core` | `pirn` | core, engine, nodes, backends, emitters, managers, streaming, triggers, viz, yaml_loader, exceptions, tapestry, replay **+ `domains/connectors` folded in** + relocated `EmbeddingProvider`/`LLMProvider` (`pirn.core.providers`) | `sweet_tea` | 8 + 3 |
| `pirn-signal` | `pirn_signal` | `pirn/domains/signal` (standalone) | `pirn-core` | ~111 |
| `pirn-data` | `pirn_data` | `pirn/domains/data` | `pirn-core` | ~175 |
| `pirn-ml` | `pirn_ml` | `pirn/domains/ml` | `pirn-core`, **`pirn-data`** | ~116 |
| `pirn-agents` | `pirn_agents` | `pirn/domains/agents` | `pirn-core` | ~136 |
| `pirn-health` | `pirn_health` | `pirn/domains/health` | `pirn-core` | ~115 |
| `pirn-oilgas` | `pirn_oilgas` | `pirn/domains/oilgas` | `pirn-core` | ~95 |

Per-package extras: `pirn-core` carries all connector/backend extras (sqlite/postgres/s3/gcs/kafka/valkey/zstd/… + `all-db`/`all-storage`/`all-stream`); `signal`→scipy/pywavelets/librosa; `data`→pandas/pyarrow + tier/lakehouse extras; `ml`→numpy/pandas/scikit-learn (+ optional torch/tensorflow/xgboost); `agents`→user-supplied; `health`→pydicom/mne/nibabel/… (+ `mri`/`genomics`); `oilgas`→segyio/lasio/resfo. Knot counts are sizing signals, not contractual.

## Documents in This Package

| Doc | Purpose |
|-----|---------|
| [PRD.md](./PRD.md) | Problem, goals/non-goals, target package list, per-package dependency mapping, blast-radius strategy, high-level phasing, success metrics, risks, open questions. |
| [ADR.md](./ADR.md) | Architectural decisions (ADR-1 workspace/8 packages, ADR-2 connectors fold, ADR-3 edge resolution, ADR-4 registry self-registration, ADR-5 compat shim, ADR-6 versioning, ADR-7 phasing) with rationale and consequences. |
| [FEATURES.md](./FEATURES.md) | Ordered, dependency-aware work breakdown (SCD-01…SCD-29) across six phases — the follow-up issue backlog and critical path. |
| [PACKAGING_MIGRATION.md](./PACKAGING_MIGRATION.md) | DevOps execution plan: root workspace `pyproject.toml`, per-package skeletons, shared tool-config, CI matrix, Docker, lockstep versioning, N-wheel publish. |
| [IMPORT_MIGRATION.md](./IMPORT_MIGRATION.md) | Codemod strategy for `pirn.domains.<x>` → `pirn_<x>` (and `connectors` → `pirn.connectors`): mapping table, ground-truth hit counts, relocated-symbol overrides, per-phase green-tree approach. |
| [REVIEW.md](./REVIEW.md) | Principal-engineer plan review: verdict, one blocker, two major issues, six minors, and what is validated. |

## Review Verdict: **Ready-with-changes**

The plan is thorough and internally coherent (packaging model, connectors fold, edge resolution, FEATURES sequencing all validated). Before execution starts (SCD-01 → SCD-02), three corrections are required:

- **BLOCKER (B1):** ADR-4's "globally unique knot class names" premise is false; ≥5 lowercased knot keys already collide across domains under today's single `library="pirn"` (`bandpassfilter`, `notchfilter`, `databaseconnectionpoolknot`, `messagebrokerknot`, `freshnesscheck`). R1 does not regress this, but the plan must stop asserting uniqueness and state a resolution rule (audit-and-assert in CI / per-domain `label=` / rename). Strengthen SCD-01 to *resolve*, not merely document.
- **MAJOR (M1):** Replace `from sweet_tea import Registry` → `from sweet_tea.registry import Registry` in every registration/shim sample (the top-level import is empty and raises `ImportError`).
- **MAJOR (M2):** Update the PRD Target Package List to the ADR-3 broken-edge graph (`pirn-agents → pirn-core`, `pirn-health → pirn-core`).

Re-review of B1's resolution plus the M1/M2 corrections is required before unblocking SCD-01 → SCD-02.

## Critical-Path Execution Order (from FEATURES.md — all deferred)

```
SCD-01 (registry spike, gate) → SCD-02 (workspace scaffold) → SCD-05 (connector interfaces → core)
→ SCD-06 (backends/codecs behind extras) → SCD-08 (break agents→ml: EmbeddingProvider → core)
→ SCD-13 (extract data) → SCD-14 (extract ml, →data) → SCD-16 (extract health)
→ SCD-18/SCD-19 (compat shim + registry helper) → SCD-24 (per-package CI matrix)
→ SCD-27 (lockstep version stamping) → SCD-28 (build & publish N wheels)
```

Phase order: **0** scaffold → **1** connectors fold → **2** residual edges → **3** extract domains (topological: signal → oilgas ‖ data → ml ‖ agents → health) → **4** import rewrite / compat / registry → **5** CI / versioning / publish. `signal` extracts first to de-risk the recipe; `oilgas` and `agents` parallelize with the data→ml spine once their deps land. **29 work items, all execution, all deferred to follow-up issues off #51.**
