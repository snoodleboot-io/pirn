# PRD: Domain Knot Libraries

**Status:** Complete
**Completed:** 2026-05-15
**Branch:** feat/domain-gap-remediation-plan

---

## Problem

Pirn's core knot primitives (Source, Sink, Aggregator, Branch, Gate, SubTapestry) are domain-agnostic. Users working in data engineering, agentic systems, ML, healthcare, signal processing, or oil and gas had to build all domain-specific wiring from scratch — creating friction, inconsistency, and a steep learning curve.

## Goal

Ship seven standardized domain knot libraries: curated, pre-built, KnotRegistry-registered collections that provide idiomatic building blocks for the most common use cases. All libraries ship under `pirn/domains/<name>/` with heavy dependencies isolated via per-domain optional extras.

## Success Criteria (all met)

- All seven domain knot libraries ship under `pirn/domains/`
- Every knot's `process()` calls real computation — no hollow shells
- Heavy dependencies isolated via optional extras (`pirn[health]`, `pirn[signal]`, etc.)
- Each domain `__init__.py` raises `ImportError` with install hint when extras missing
- All ~470 hollow knots replaced with real algorithm implementations
- SubTapestry specializations conform to the SubTapestry contract across all domains
- Assembler/disassembler pattern enforced; all ingestors deleted
- Payload pattern audit passed for agents, data, and connectors

## What Each Domain Delivered

| Domain | Approx Files | Key Capabilities |
|--------|-------------|-----------------|
| `pirn.domains.data` | ~100 | Tiered architecture (Tier 1 dict → Tier 2 Polars/Pandas/DuckDB/DataFusion → Tier 2.5 Vaex/Modin → Tier 3 Ibis/Spark/Ray/Dask → streaming Pathway/Bytewax → Tier 4 Lance/Eland); quality, lakehouse, SCD, incremental, medallion, data vault, feature engineering |
| `pirn.domains.agents` | ~175 | LLM calls, memory, tool routing, ReAct, RAG, multi-agent, guardrails, structured output, chain-of-thought, reflection, human-in-the-loop, LoopSubTapestry |
| `pirn.domains.ml` | ~147 | Data prep, feature engineering, training, evaluation (SHAP + fairness audit), deployment (ModelRegistrar, Predictor, shadow deployment); 4 intentional abstract interfaces remain |
| `pirn.domains.health` | ~129 | EEG/MEG (MNE), MRI (nibabel/nilearn), genomics, clinical/EHR, wearables, pathology, clinical trials; FHIR R4, OMOP CDM, DICOM, NIfTI, BIDS, CDISC; 1 intentional gap (OMOP CDM mapper blocked on vocab DB) |
| `pirn.domains.oilgas` | ~109 | Seismic interpretation (segyio), well/petrophysics (lasio), reservoir engineering, production ops, facilities integrity, geospatial (resfo + stdlib) |
| `pirn.domains.connectors` | ~265 | 80+ backends: relational DBs (Postgres, MySQL, MSSQL, Oracle, Clickhouse, BigQuery, Databricks, DuckDB, Dremio), object storage (S3, GCS, Azure, HDFS, local), streaming (Kafka, PubSub, Kinesis, RabbitMQ, Azure Service Bus, Valkey), document/graph/time-series DBs, SaaS APIs (Salesforce, HubSpot, Stripe, GitHub, Jira, Shopify, Twilio, Zendesk, Mixpanel, Amplitude, Airtable, Google Analytics), BI/catalog (dbt, Airbyte, Fivetran, DataHub, Alation, OpenMetadata), observability (PagerDuty, Slack, Teams, Discord) |
| `pirn.domains.signal` | ~85 | Filters (IIR/FIR/adaptive/nonlinear), spectral (FFT/STFT/wavelet), audio (librosa), beamforming, resampling, separation, statistical — real scipy/numpy/librosa/pywt/padasip calls |

## Deferred (Out of Scope)

- **Extended connectors:** Priority-tier connectors shipped; ~48 connector classes remain as placeholders pending the connectors-infrastructure initiative.
- **Per-element lineage for Map-distributed knots:** Deferred; requires engine changes.
- **SubTapestry `@subtapestry` decorator:** Not implemented; users subclass directly.
- **Cross-tier bridging knots** (`DataBatchToPolars`, `PolarsToArrow`, etc.): Deferred pending demonstrated need.
- **ML abstract interfaces:** `lineage_store.py`, `embedding_provider.py`, `image_encoder_provider.py`, `feature_store_provider.py` remain abstract by design.
