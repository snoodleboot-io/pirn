# AGENTIC_USE.md Remediation

**Branch:** feat/documentation-corrections  
**Opened:** 2026-05-19  
**Scope:** Correctness fixes, coverage gaps, and missing files in the AGENTIC_USE.md hierarchy

---

## What this tracks

`AGENTIC_USE.md` files guide an agent consuming this repo on how to use the library. The hierarchy has one file at the repo root, one per domain, and one per complex sub-package. This document tracks every known error, gap, and missing file found during the 2026-05-19 audit.

---

## AGENTIC_USE.md template

Every `AGENTIC_USE.md` file — regardless of depth — must contain the following sections in order. Omit a section only if it genuinely does not apply (e.g. a leaf package with no sub-packages has no "Sub-package index"). Leave no section empty; if there is nothing to say, the section should not exist.

### Required sections

**1. One-line scope statement (no heading)**  
The very first line of the file. States what this package does and — critically — what it does NOT do. Agents use this to decide whether to keep reading.

> `pirn.domains.agents.specializations.rag provides retrieval-augmented generation pipelines built on top of the agents tier knots; it does not implement vector storage or embedding — those are user-supplied via MemoryStore.`

---

**2. `## Mental model`**  
2–4 sentences explaining the conceptual framing an agent needs before reading anything else. What is the core abstraction? What is the execution order? What are the invariants?

---

**3. `## Install` (if the package requires an optional extra)**  
The exact `pip install pirn[extra]` command. Include any provider/backend packages the user must add separately. Omit entirely if the package is part of the base install.

---

**4. `## Source map`**  
A fenced code block showing the directory tree with one-line annotations per file. Format:

```
pirn/path/to/package/
├── file_a.py     ClassName    — one-line description
├── file_b.py     ClassName    — one-line description
└── sub/
    └── file_c.py ClassName    — one-line description
```

Rules:
- Every public class or function gets one line.
- Private helpers (`_foo.py`) are omitted unless an agent would need to know they exist.
- Sub-packages that have their own `AGENTIC_USE.md` are listed with a `→ see AGENTIC_USE.md` annotation rather than expanded inline.

---

**5. `## Interfaces` (if the package defines abstract interfaces the user must implement)**  
One subsection per interface. Each subsection contains:
- The contract in plain English (what you must implement, what you must not do)
- A minimal concrete implementation example

---

**6. `## Canonical pattern` or `## Canonical pipeline chain`**  
The 80% wiring example. A complete, runnable code snippet showing the most common use of this package. No hand-waving — real import paths, real constructor signatures.

---

**7. `## Sub-package index` (if the package has sub-packages)**  
A table:

| Sub-package | What it contains | Guide |
|-------------|-----------------|-------|
| `rag/` | RAG pipeline variants | [AGENTIC_USE.md](rag/AGENTIC_USE.md) |

---

**8. `## Anti-patterns`**  
The 3–5 mistakes agents and engineers most commonly make with this package. Each entry:
- **Name** in bold — what the mistake looks like
- What makes it wrong
- What to do instead

---

**9. `## Constraints and gotchas`**  
Bullet list of hard limits, surprising defaults, and non-obvious interactions. These are facts, not advice — things that will silently burn an agent if not known.

---

**10. `## Quick reference`**  
A two-column table: `Task | How`. Every public knot or callable in the package gets one row. This is the section agents scan first.

---

**11. Footer**  
Last line of the file. Relative link back to the nearest parent `AGENTIC_USE.md`:

```
*See also: [pirn/domains/agents AGENTIC_USE.md](../AGENTIC_USE.md)*
```

For the root file, the footer instead carries the version stamp (maintained by the `stamp-agentic-use-version` pre-commit hook):

```
*Generated for agent use. Covers pirn 0.x*
```

---

## Completed fixes (this branch)

### Root `AGENTIC_USE.md` — source map errors

- [x] **`branch.py` → `branch/branch.py`**
- [x] **Remove dead `map_knot.py` entry**
- [x] **`reduce.py` → `reduce_.py`**

### `pirn/domains/agents/AGENTIC_USE.md`

- [x] **`ApprovalGate` → `ApprovalCheck` in source map**
- [x] **`ApprovalGate` → `ApprovalCheck` in quick reference table**
- [x] **Back-link `../../AGENTIC_USE.md` → `../../../AGENTIC_USE.md`**
- [x] **Add `human_in_the_loop/` usage example**
- [x] **Add `plan_and_execute/` usage example**

---

## Missing files — framework layer

These sub-trees have no `AGENTIC_USE.md` at any level. The root file gives a one-line mention of each; that is not enough for an agent to use them.

- [x] **`pirn/nodes/AGENTIC_USE.md`**  
  Gate, Branch, Map/ZipMap/DictMap, Aggregator, Reduce, Continuation. These are the structural knots every pipeline uses; they are scattered across root examples but never explained together.

- [x] **`pirn/backends/AGENTIC_USE.md`**  
  8 backends across 3 protocols (TapestryStore, RunHistory, DataStore). Swap patterns, durable vs in-memory trade-offs, S3/GCS/Azure object store setup, SQLite vs Postgres vs ValKey.

- [x] **`pirn/emitters/AGENTIC_USE.md`**  
  5 emitters (Log, Kafka, OpenTelemetry, Webhook, ValKey). Event hook contract, error isolation guarantee, how to compose multiple emitters.

- [x] **`pirn/triggers/AGENTIC_USE.md`**  
  4 triggers (Cron, Webhook/HTTP, Kafka, ValKey). `run_forever` contract, webhook auth requirements, trigger lifecycle.

- [x] **`pirn/streaming/AGENTIC_USE.md`**  
  `run_stream` vs `run` execution model — this is a different contract from the rest of the framework and currently only a single constraint bullet in the root file.

- [x] **`pirn/engine/dispatchers/AGENTIC_USE.md`**  
  5 dispatchers (Local, Thread, Dask, Ray, Celery). When to use each, configuration, resource management.

---

## Missing files — connectors (entire domain uncovered)

`pirn/domains/connectors/` has 252 files across 14 sub-packages and zero `AGENTIC_USE.md` coverage at any level.

- [x] **`pirn/domains/connectors/AGENTIC_USE.md`**  
  Top-level: ConnectionConfig, connection pool, object store interface, DSN scrubbing, the knots sub-package. Mental model for how connectors wire into a tapestry.

- [x] **`pirn/domains/connectors/databases/AGENTIC_USE.md`** (26 files)
- [x] **`pirn/domains/connectors/file_formats/AGENTIC_USE.md`** (96 files — largest single sub-package in the repo)
- [x] **`pirn/domains/connectors/messaging/AGENTIC_USE.md`** (13 files)
- [x] **`pirn/domains/connectors/object_storage/AGENTIC_USE.md`** (11 files)
- [x] **`pirn/domains/connectors/streaming/AGENTIC_USE.md`** (16 files)
- [x] **`pirn/domains/connectors/saas/AGENTIC_USE.md`** (25 files)
- [x] **`pirn/domains/connectors/timeseries/AGENTIC_USE.md`** (11 files)
- [x] **`pirn/domains/connectors/document/AGENTIC_USE.md`** (13 files)
- [x] **`pirn/domains/connectors/graph/AGENTIC_USE.md`** (7 files)
- [x] **`pirn/domains/connectors/bi_catalog/AGENTIC_USE.md`** (13 files)
- [x] **`pirn/domains/connectors/observability/AGENTIC_USE.md`** (9 files)

---

## Missing files — agents domain (deeper layer)

- [x] **`pirn/domains/agents/specializations/AGENTIC_USE.md`**  
  134 files across 15 sub-packages. The agents domain file covers the core tiers but the specializations are a source map and quick-reference table only — no prose, no wiring examples, no gotchas per pattern. This file should be a sub-package index + mental model for when to use which specialization family. Each complex sub-package below should also get its own file.

- [x] **`pirn/domains/agents/specializations/rag/AGENTIC_USE.md`** (17 files)
- [x] **`pirn/domains/agents/specializations/multi_agent/AGENTIC_USE.md`** (11 files)
- [x] **`pirn/domains/agents/specializations/guardrails/AGENTIC_USE.md`** (12 files)
- [x] **`pirn/domains/agents/specializations/structured_output/AGENTIC_USE.md`** (12 files)
- [x] **`pirn/domains/agents/specializations/memory_patterns/AGENTIC_USE.md`** (13 files)
- [x] **`pirn/domains/agents/specializations/document_processing/AGENTIC_USE.md`** (16 files)
- [x] **`pirn/domains/agents/specializations/specialized_agents/AGENTIC_USE.md`** (13 files)

---

## Missing files — data domain (deeper layer)

- [x] **`pirn/domains/data/specializations/AGENTIC_USE.md`**  
  93 files across 12 sub-packages (medallion, SCD, incremental, data vault, feature engineering, etc.). The data domain file covers the tier model but not the specialization patterns.

- [x] **`pirn/domains/data/frames/AGENTIC_USE.md`** (60 files — Tier 2 Polars/pandas knots)
- [x] **`pirn/domains/data/lazy/AGENTIC_USE.md`** (37 files — Tier 3 lazy/push-down knots)
- [x] **`pirn/domains/data/lakehouse/AGENTIC_USE.md`** (13 files)

---

## Missing files — ml domain (deeper layer)

- [x] **`pirn/domains/ml/specializations/AGENTIC_USE.md`**  
  95 files across 6 sub-packages (evaluation, production, training, experiments, feature_engineering, task_pipelines).

---

## Missing files — vertical domains (sub-package layer)

Health, oil & gas, and signal each have sub-packages large enough to need their own files. An agent working in one vertical needs types, assembler/disassembler conventions, and wiring patterns specific to that sub-package.

### health

- [x] **`pirn/domains/health/genomics/AGENTIC_USE.md`** (27 files)
- [x] **`pirn/domains/health/clinical/AGENTIC_USE.md`** (21 files)
- [x] **`pirn/domains/health/mri/AGENTIC_USE.md`** (22 files)
- [x] **`pirn/domains/health/eeg_meg/AGENTIC_USE.md`** (16 files)
- [x] **`pirn/domains/health/trials/AGENTIC_USE.md`** (12 files)
- [x] **`pirn/domains/health/wearables/AGENTIC_USE.md`** (9 files)

### oilgas

- [x] **`pirn/domains/oilgas/seismic/AGENTIC_USE.md`** (21 files)
- [x] **`pirn/domains/oilgas/well/AGENTIC_USE.md`** (20 files)
- [x] **`pirn/domains/oilgas/production/AGENTIC_USE.md`** (18 files)
- [x] **`pirn/domains/oilgas/reservoir/AGENTIC_USE.md`** (13 files)
- [x] **`pirn/domains/oilgas/integrity/AGENTIC_USE.md`** (10 files)
- [x] **`pirn/domains/oilgas/geospatial/AGENTIC_USE.md`** (8 files)

### signal

- [x] **`pirn/domains/signal/filters/AGENTIC_USE.md`** (26 files)
- [x] **`pirn/domains/signal/spectral/AGENTIC_USE.md`** (15 files)
- [x] **`pirn/domains/signal/audio/AGENTIC_USE.md`** (13 files)
- [x] **`pirn/domains/signal/resampling/AGENTIC_USE.md`** (13 files)
- [x] **`pirn/domains/signal/wavelets/AGENTIC_USE.md`** (12 files)
- [x] **`pirn/domains/signal/adaptive/AGENTIC_USE.md`** (9 files)
- [x] **`pirn/domains/signal/separation/AGENTIC_USE.md`** (8 files)
- [x] **`pirn/domains/signal/nonlinear/AGENTIC_USE.md`** (8 files)
- [x] **`pirn/domains/signal/statistical/AGENTIC_USE.md`** (9 files)

---

## Additional gap (separate ticket)

`docs/domains/agents.md` (human-facing docs) has a stale specializations table — 7 sub-packages and 3 RAG pipelines are missing. Out of scope for this ticket.

---

## Summary

| Category | Missing files |
|----------|--------------|
| Framework layer (nodes, backends, emitters, triggers, streaming, dispatchers) | 6 |
| Connectors (entire domain) | 12 |
| Agents specializations | 8 |
| Data deeper layers | 4 |
| ML specializations | 1 |
| Health sub-packages | 6 |
| Oil & gas sub-packages | 6 |
| Signal sub-packages | 9 |
| **Total** | **52** |
