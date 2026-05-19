# Lineage Gaps — Audit and Roadmap

**Status:** In Planning  
**Date:** 2026-05-19  
**Author:** John Aven

---

## The 7 W's — Current State

| Dimension | Field(s) | Status |
|---|---|---|
| **WHO** | `actor` | Gap — field exists, never populated |
| **WHAT** | tapestry graph, `lineage`, `knot_sources` | Covered |
| **WHEN** | `started_at`, `finished_at` | Covered |
| **WHERE** | `environment` (hostname auto-populated) | Covered |
| **WHY** | `trigger` | Gap — field exists, never populated |
| **HOW** | `dispatcher`, `runtime_info`, `knot_sources` | Covered |
| **WHICH** | `knot_sources` (per-knot), `knot_config_hash` (per-knot) | Partial — no run-level pipeline version or git SHA |

## Data Lineage Layer — Current State

The 7 W's covers run-level provenance. The data lineage layer (what happened to the data) is entirely absent.

| Sub-level | Description | Status |
|---|---|---|
| **Dataset lineage** | Which datasets were read and written per knot | Missing |
| **Column lineage** | Which input columns map to which output columns | Missing |
| **Value lineage** | Individual record tracing source → output | Out of scope (v1) |

---

## Gap Summary

| Gap | Initiative | Priority | Status |
|---|---|---|---|
| WHO — `actor` never populated | `who-identity/` (completed) | High | ✅ Shipped |
| WHY — `trigger` never populated | `who-identity/` (completed) | High | ✅ Shipped |
| WHICH — no run-level version/git SHA | `who-identity/` (completed) | Medium | ✅ Shipped — `vcs_commit` in `runtime_info` |
| Dataset lineage — no input/output asset tracking | `backlog/dataset-lineage/` | High | Backlog |
| Column lineage — no column-level mapping | `backlog/column-lineage/` | Medium | Backlog |

---

## Initiatives

### 1. WHO + WHY Identity (in progress)
See `WHO_IDENTITY_PRD.md`, `WHO_IDENTITY_ADR.md`, `WHO_IDENTITY_FEATURE_BREAKDOWN.md`.

`trigger` is already in F-1 of the PRD — both gaps close together.

### 2. WHICH — Run-Level Version Capture
New initiative. Captures at the run level: pirn version (already in `runtime_info`), git SHA of the calling project, and pipeline/tapestry version tag. Lightweight — no new abstractions needed, just auto-population at `RunContext` construction.

### 3. DATA_LINEAGE — Dataset and Column Lineage
Largest gap. See design discussion below.

---

## Data Lineage Design Discussion

See `DATA_LINEAGE_DESIGN.md` (to be created after design discussion is settled).
