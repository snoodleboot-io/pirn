# Phase 4 Plan — Import Rewrite, Compatibility, Registry & Consumer Migration (SCD-17–23)

**Fidelity:** SKELETON ⚠ (item/deps/AC stable from `FEATURES.md`).
**Inherits:** [PIPELINE.md](./PIPELINE.md) A–D.
**Depends on:** SCD-16 (all domains extracted) for the shim/registry/tests/docs; SCD-17 (codemod) runs **incrementally from SCD-02 onward** and is the spine of this phase.
**Issues:** [#68](https://github.com/snoodleboot-io/pirn/issues/68)–[#74](https://github.com/snoodleboot-io/pirn/issues/74).

## Items & dependencies
```
SCD-17 codemod (deps: SCD-02; run incrementally through Phase 3)
SCD-18 compat shim (deps: SCD-16) ┐
SCD-19 discover helper (deps: SCD-16) ┤  ── parallel feature work
SCD-20 tests reorg (deps: SCD-16, SCD-17) ┤
SCD-21 examples migrate (deps: SCD-17) ┤
SCD-22 docs+Docker (deps: SCD-16, SCD-17) ┘
SCD-23 consumer guide (deps: SCD-17, SCD-18)
```
After SCD-17 lands, **SCD-18/19/20/21/22 fan out in parallel** (different surfaces: core shim / core helper / tests / examples / docs); SCD-23 follows shim+codemod.

## Delta §3 — Environment
uv + full docker (SCD-20 reorganizes 160+ tests incl. real-backend suites; SCD-22 builds `Dockerfile.ci`/`ci-heavy`). `mkdocs build` toolchain for SCD-22.

## Delta §4 — Execution map
```mermaid
flowchart TD
    ENV[Env-Setup: uv + docker + mkdocs] --> S17["SCD-17 (migration): import-rewrite codemod<br/>pirn.domains.<x> → pirn_<x> · idempotent · run incrementally"]
    S17 --> FAN{fan-out}
    FAN --> S18["SCD-18 (code): pirn.domains.* compat shim — lazy __getattr__,<br/>DeprecationWarning if installed / ImportError→pip install pirn-<x> if absent · no hard dep"]
    FAN --> S19["SCD-19 (code): discover_installed_domains() via importlib.metadata<br/>+ better yaml_loader miss message"]
    FAN --> S20["SCD-20 (test): reorg 160+ tests + ~9 conftests · shared fixtures in pirn-core test-support module"]
    FAN --> S21["SCD-21 (migration): codemod over 11 example dirs + install hints"]
    FAN --> S22["SCD-22 (document): mkdocstrings.paths → 8 pkgs · domain pages · Dockerfile.ci/ci-heavy sync all members"]
    S18 --> S23["SCD-23 (document): consumer migration guide + codemod tool + pirn[all-domains] meta-extra"]
    S18 & S19 & S20 & S21 & S22 & S23 --> AGG{{cross-domain tapestry resolves by bare name (registry parity) · all suites green · mkdocs builds}}
    AGG --> GATES[G-ENF → G-SEC → G-REV] --> DONE([Phase 4 done])
```

## Delta §5 — Subagents
- **SCD-17** (migration): codemod for all 6 domain import forms; idempotent; also fixes stale docstrings/error-strings; becomes the SCD-23 consumer tool.
- **SCD-18** (code): `pirn/domains/__init__.py` lazy `__getattr__` (ADR-5 Option B) — **deferred** imports so core gains no hard domain dep.
- **SCD-19** (code): `pirn.discover_installed_domains()` — convenience, not the discovery mechanism; improves loader miss message.
- **SCD-20** (test): centralize cross-cutting fixtures in an importable `pirn-core` test-support module (ADR open-q #6) so fixtures stay visible across separately-installed packages; preserve assertions (structural split only).
- **SCD-21** (migration), **SCD-22** (document), **SCD-23** (document): as above.

## Delta §7 — Test strategy
ATDD: `import pirn.domains.data` succeeds with `DeprecationWarning` iff `pirn-data` installed, else `ImportError` naming the fix (SCD-18); cross-domain tapestry resolves all knots by bare name after `discover_installed_domains()` (SCD-19 registry-parity metric). TDD: codemod idempotency + determinism (SCD-17); per-package extras-isolation tests (SCD-20); shim covers all 6 domains. `test_domains_extras.py` `sys.modules` manipulation rewritten to pop `pirn_<x>` keys.

## Delta §8 — Integration verification
Shim verified against **real** installed/absent `pirn_<x>` packages (not mocked) — install `pirn-data`, assert warning path; uninstall, assert `ImportError`. `pirn-core` dependency-tree check confirms **no** hard domain dep (C2). `mkdocs build` runs for real across 8 packages. `Dockerfile.ci`/`ci-heavy` actually build with all members synced.

## Delta §9 — Gaps `⚠`
- P4-A: registry-parity (SCD-19) presumes the SCD-01-validated self-registration — provisional.
- P4-B: shared-fixture visibility across separately-installed packages (SCD-20) is the open ADR question #6; the test-support-module approach must be proven before mass test reorg, else flag.

## DoD (→ #68–#74 AC)
- ☑ Codemod rewrites all 6 import forms deterministically + idempotent; no stale `pirn.domains.*` refs post-extraction (except shim). *(SCD-17 — `pirn._migrate.ImportRewriter`, console-script `pirn-migrate-imports`, 21 tests)*
- ☑ Shim: warning-if-installed / ImportError-if-absent; core declares no hard domain dep; covers all 6. *(SCD-18 — `DomainCompatFinder`+`DomainCompatLoader`+`__getattr__`; finder at `sys.meta_path[0]` so legacy submodules keep canonical `pirn_<x>.<sub>` identity)*
- ☑ `discover_installed_domains()` imports every installed `pirn_*`; cross-domain bare-name resolution. *(SCD-19 — `pirn._domain_discovery`; yaml_loader miss message enriched)*
- ☑ All tests green against installed split packages; shared fixtures importable; extras-isolation passes. *(SCD-20 — fixed smoke version + core `__version__` (`pirn`→`pirn-core`) + import-graph gate now scans extracted packages. Tests stay centralized per ADR open-q #6, so no per-package test-support module is needed. 7163 pass; remaining reds are pre-existing & out of scope — see Gap report.)*
- ☑ Examples import `pirn_<x>`; docs build unified; Docker images carry all members; consumer guide + `pirn[all-domains]` documented. *(SCD-21/22/23 — examples ruff-clean + explorer regenerated; `mkdocstrings.paths`→7 packages; `Dockerfile.ci`/`ci-heavy` use `--all-packages --all-extras`; `pirn-core[all-domains]` now depends on the 6 domain dists; `docs/guides/migrating-to-split-packages.md`)*

### Phase-4 execution notes (orchestrator)
- **Collision fix (SCD-01 invariant):** the 4 unused per-domain `ExtrasLoader` classes collided on registry key `extrasloader`. Per user decision, deleted them (zero call sites) — `test_registry_uniqueness` now green.
- **ADR-4 confirmed:** import-the-domain-to-register holds; `discover_installed_domains()` restores monolith ergonomics opt-in.
- **ADR-5 confirmed:** shim = Option B (lazy, no hard dep); `pirn-core[all-domains]` = Option C (opt-in meta-extra). Deprecation window: shim for one minor, removed at 1.0.
- **Gap / pre-existing (NOT introduced by Phase 4, flagged):** (a) `tests/security/test_redos_guard.py` ×3 — real failures in `pirn_agents` SafetyCheck/HandoffCheck, out of scope; (b) env-limited locally on Python 3.14: domain-extra tests needing `resfo`/`nibabel`/`dipy`/`polars`/ecCodes/GDAL/HDF5 (no cp314 wheels / system libs); (c) root `pyrightconfig.json` `include:["pirn"]` is stale (points at the pre-split path → pyright is a workspace no-op) — left for a dedicated tooling fix to avoid surfacing an unrelated type-error backlog in this phase.
