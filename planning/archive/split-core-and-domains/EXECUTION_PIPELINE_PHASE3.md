# Phase 3 Plan — Extract Domains (SCD-11–16)

**Fidelity:** SKELETON ⚠ (item/deps/AC stable from `FEATURES.md`).
**Inherits:** [PIPELINE.md](./PIPELINE.md) A–D.
**Key design point:** this is **one plan, one recipe applied six times** — not six plans. SCD-11 (signal) de-risks the extraction recipe; SCD-12–16 reuse it with parallel lanes.
**Issues:** [#62](https://github.com/snoodleboot-io/pirn/issues/62)–[#67](https://github.com/snoodleboot-io/pirn/issues/67).

## Items, dependencies & parallelism
```
SCD-11 signal (standalone, deps: SCD-04, SCD-10) ── proves the recipe FIRST
   ├─ SCD-12 oilgas (→core, deps: SCD-11)            ⟍ parallel once SCD-11 lands
   ├─ SCD-13 data   (→core, deps: SCD-11)            ⟍ critical path (ml needs it)
   │     └─ SCD-14 ml (→core,→data, deps: SCD-13, SCD-08)
   └─ SCD-15 agents (→core, deps: SCD-08, SCD-13)
         └─ SCD-16 health (→core, deps: SCD-09, SCD-15)
```
After SCD-11 proves the recipe: **oilgas ‖ data ‖ agents** fan out; the **data→ml** spine and **agents→health** run as their deps land. Each domain is a separate mergeable PR / worktree-isolated lane.

## Shared extraction recipe (template (a)–(f), applied per domain)
For each `pirn/domains/<x>` → `packages/pirn-<x>/src/pirn_<x>/`:
- **(a)** source lands at the package `src/` path;
- **(b)** `__init__.py` calls `Registry.fill_registry(module=__name__, library="pirn")` under `SweetTeaWarning` suppression `⚠ (depends on SCD-01-validated mechanism)`;
- **(c)** domain extras declared in the package `pyproject.toml`;
- **(d)** `ExtrasLoader` moves with the domain; messages updated to `pirn_<x>`;
- **(e)** imports clean with no extras; clean install-hint `ImportError` when a required extra is missing;
- **(f)** SCD-17 codemod updates in-repo references to this domain.

## Delta §3 — Environment
Full docker test env + uv, plus **per-domain heavy extras**: signal→scipy/pywavelets/librosa/padasip; oilgas→segyio/lasio/resfo; data→pandas/pyarrow + tier/lakehouse; ml→numpy/pandas/scikit-learn (+torch/tf optional); agents→user-supplied; health→pydicom/mne/nibabel/pyfaidx/pysam (+mri/genomics). Env-Setup syncs the extras for whichever domains are in-flight.

## Delta §4 — Execution map
```mermaid
flowchart TD
    ENV[Env-Setup: uv + docker + per-domain extras] --> S11["SCD-11 signal — run recipe (a)-(f) FIRST, de-risk"]
    S11 --> AGGr{{recipe validated · bare-name signal YAML resolves · install-isolation: only core+scipy/...}}
    AGGr --> FAN{fan-out — recipe reused}
    FAN --> S12[SCD-12 oilgas →core]
    FAN --> S13[SCD-13 data →core]
    FAN --> S15a[SCD-15 agents →core]
    S13 --> S14[SCD-14 ml →core,→data]
    S15a --> S16[SCD-16 health →core]
    S13 --> S15a
    S12 & S14 & S16 --> AGG{{per-domain: template (a)-(f) · clean-env install isolation asserted}}
    AGG --> GATES[G-ENF → G-SEC → G-REV per PR] --> DONE([Phase 3 done → all domains extracted])
```

## Delta §5 — Subagents
One **refactor-agent extraction subagent per domain** (worktree-isolated, since they mutate the tree in parallel), each running the recipe template; **migration-agent** runs SCD-17 incrementally after each extraction so the tree stays green. SCD-14 (ml) additionally **declares the retained `pirn-ml → pirn-data` hard dep** and repoints `dataset_loader` to `pirn_data` + `EmbeddingProvider` to `pirn.core.providers`.

## Delta §7 — Test strategy
Per domain: ATDD = "clean-env `pip install pirn-<x>` pulls only the expected tree" (install-isolation metric); a bare-name `<x>`-knot YAML resolves after `import pirn_<x>`. TDD = template (e) extras-missing → clean `ImportError`. `src/` layout forces tests against the **installed** wheel, not in-tree source. SCD-14: assert no `pirn_data → pirn_ml` edge.

## Delta §8 — Integration verification
Clean-venv install per domain → assert resolved dependency tree (signal pulls nothing from data/ml/health/oilgas; ml transitively pulls data). Real-backend tests per domain still green. Cross-domain tapestry (data+ml+agents) resolves by bare name.

## Delta §9 — Gaps `⚠`
- P3-A `⚠`: the `fill_registry` self-registration in (b) is exactly what SCD-01 validates — if the gate amends ADR-4, (b) changes for all six. Provisional until gate closes.
- P3-B: data is the largest (~175 knots, 8 specializations); its extraction subagent may itself fan out by specialization. Flag if scope exceeds one worktree cleanly.

## DoD (→ #62–#67 AC)
- ☐ Each domain: recipe (a)–(f) satisfied; depends only on `pirn-core` (except ml→data); clean-env install isolation asserted; bare-name YAML resolves. *(SCD-11–16)*
- ☐ ml declares `pirn-core` + `pirn-data`; `dataset_loader` imports from `pirn_data`; `EmbeddingProvider` from core; one-directional acyclic. *(SCD-14)*
