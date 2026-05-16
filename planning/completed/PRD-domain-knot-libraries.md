# PRD: Domain Knot Libraries

**Status:** Complete
**Completed:** 2026-05-15
**Branch:** feat/domain-gap-remediation-plan
**Source:** planning/archive/domain-knot-libraries-prd.md

---

## Problem Statement

Pirn's core knot primitives (Source, Sink, Aggregator, Branch, Gate, SubTapestry) are domain-agnostic. Users working in data engineering, agentic systems, ML engineering, healthcare, signal processing, or oil and gas must build all domain-specific wiring from scratch. This creates friction, inconsistency across projects, and a steep learning curve.

The initial PRD proposed seven standardized domain knot libraries — curated, pre-built, and KnotRegistry-registered collections that provide idiomatic building blocks for the most common use cases, shipping inside `pirn/domains/<name>/` with heavy dependencies isolated via per-domain optional extras.

---

## Goals

- Reduce time-to-first-working-pipeline for new users in each domain
- Establish shared vocabulary and data types within each domain
- Make KnotRegistry the natural entry point (YAML-composable out of the box)
- Remain additive — zero changes to pirn core

---

## Success Criteria (all met)

- All seven domain knot libraries ship under `pirn/domains/` as first-party code
- Every knot's `process()` calls real computation libraries — no hollow shells
- Heavy dependencies isolated via optional extras (`pirn[health]`, `pirn[signal]`, etc.)
- Each domain's `__init__.py` raises `ImportError` with install hint if extras missing
- All ~470 hollow knots identified in the audit replaced with real algorithm implementations
- SubTapestry specializations in every domain conform to the SubTapestry contract
- Assembler/Disassembler pattern enforced — ingestors deleted, bridge knots present
- Payload pattern audit passed for agents, data, and connectors

---

## Domains Delivered

| Domain | Status | Approx Files | Key Capabilities |
|--------|--------|-------------|-----------------|
| `pirn.domains.agents` | Complete | ~175 | LLM calls, memory, tool routing, ReAct, RAG, multi-agent, guardrails, structured output |
| `pirn.domains.data` | Complete | ~100 | Tiered architecture (Tier 1 dict → Tier 2 Polars/Pandas/DuckDB/DataFusion → Tier 3 Ibis/Spark → streaming); quality, lakehouse, validation |
| `pirn.domains.connectors` | Complete | ~265 | 80+ backends: databases (asyncpg, Snowflake, BigQuery, DuckDB, …), object storage (S3, GCS, Azure), streaming (Kafka, PubSub, RabbitMQ), SaaS, BI/catalog, observability |
| `pirn.domains.signal` | Complete | ~85 | Real scipy/numpy/librosa/pywt/padasip calls; spectral, filtering (IIR/FIR/adaptive/nonlinear), wavelets, beamforming, audio/speech |
| `pirn.domains.health` | Complete | ~129 | Real scipy/sklearn/MNE computation; EEG/MEG, MRI, genomics, clinical/EHR, wearables, pathology, clinical trials; FHIR R4, OMOP CDM, DICOM, NIfTI, BIDS, CDISC |
| `pirn.domains.ml` | Complete | ~147 | Real sklearn/xgboost/shap calls; data prep, feature engineering, training, evaluation (fairness audit, SHAP), deployment (ModelRegistrar, Predictor, shadow deployment) |
| `pirn.domains.oilgas` | Complete | ~109 | Real segyio/lasio/resfo calls; seismic interpretation, well/petrophysics, reservoir engineering, production ops, facilities integrity, geospatial |

---

## Data Domain: Tiered Architecture

The data domain ships with a tiered architecture (Position B: pirn as orchestrator). Knots are thin wrappers around library-native operations — each tier is a parallel, independent transform set:

| Tier | Contract | Engines |
|------|----------|---------|
| 1 | `DataBatch` (dict-based) | Pure Python — fallback, fixtures, glue |
| 2 | Native frames | Polars (first), Pandas, DuckDB, DataFusion, PyArrow |
| 2.5 | Out-of-core | Vaex, Modin |
| 3 | Push-down / lazy | Ibis (first), PySpark, Ray Data, Dask |
| 3-stream | Streaming | Pathway, Bytewax |
| 4 | Specialized | Lance, Eland |

---

## Out of Scope

The following were explicitly deferred and remain as future work:

- **Connectors infrastructure — extended SaaS and BI/catalog connectors:** The priority tier (Postgres, SQLite, DuckDB, S3, Kafka, Valkey) shipped. The full 50-connector surface defined in the original PRD is partially implemented; remaining connectors are placeholders.
- **Per-element lineage for Map-distributed knots:** Each Map element shares the knot's single lineage record. Per-element records require engine changes tracked separately.
- **SubTapestry `@subtapestry` decorator:** Not implemented; users subclass directly.
- **OMOP CDM mapper in health domain:** Blocked on OMOP vocabulary database requirement. Single remaining intentional gap.
- **ML domain abstract interfaces (4 files):** `lineage_store.py`, `embedding_provider.py`, `image_encoder_provider.py`, `feature_store_provider.py` remain abstract by design — concrete implementations are user responsibility.
- **Cross-tier bridging knots** (`DataBatchToPolars`, `PolarsToArrow`, etc.): Deferred pending demonstrated user need across two tiers simultaneously.
