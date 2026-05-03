# PRD: Domain Knot Libraries

**Status:** Draft  
**Date:** 2026-04-30  
**Branch:** feat/domain-knot-libraries

---

## Overview

Pirn's core knot primitives (Source, Sink, Aggregator, Branch, Gate, SubTapestry) are domain-agnostic. Users working in data engineering, agentic systems, or ML engineering must currently build all domain-specific wiring from scratch. This creates friction, inconsistency across projects, and a steep learning curve.

This PRD proposes **seven standardized domain knot libraries** — curated, pre-built, and KnotRegistry-registered collections that provide idiomatic building blocks for the most common use cases:

1. **`pirn.domains.data`** — Data Engineering & Analytics Engineering
2. **`pirn.domains.agents`** — Agentic Pipelines & Patterns
3. **`pirn.domains.ml`** — ML Engineering & Data Science
4. **`pirn.domains.connectors`** — Cross-cutting Source/Sink connectors (databases, object storage, streaming, SaaS, BI/catalog, observability)
5. **`pirn.domains.health`** — Healthcare, Genomics, Neuroimaging, EEG/MEG, Wearables, Pathology, Clinical Trials
6. **`pirn.domains.signal`** — Digital Signal Processing (spectral, filtering, wavelets, adaptive, source separation)
7. **`pirn.domains.oilgas`** — Oil & Gas (seismic, well, reservoir, production ops, integrity, geospatial)

All seven libraries ship inside the `pirn` package as `pirn/domains/<name>/`. Heavy dependencies are isolated via per-domain optional extras (`pip install pirn[health]`, `pirn[snowflake]`, etc.); the base install stays slim. Each library ships with typed knots, standardized data contracts (dataclasses), and example pipelines demonstrating composition.

---

## Goals

- Reduce time-to-first-working-pipeline for new users in each domain
- Establish shared vocabulary and data types within each domain
- Make KnotRegistry the natural entry point (YAML-composable out of the box)
- Remain additive — zero changes to pirn core

---

## Non-Goals

- Replacing or wrapping third-party frameworks (no dbt integration, no LangChain wrapper)
- Providing production-grade connectors (those belong in optional extras or plugins)
- Prescribing execution backends (Celery/Dask/Ray choice stays with the user)

---

## Domain 1: `pirn.domains.data` — Data Engineering / Analytics Engineering

> **Architecture note:** The data domain is *tiered*. Pirn is an
> orchestrator; engines do the work. Knots are thin wrappers around
> library-native operations (Polars, Ibis, Pandas, DuckDB, PySpark, Ray,
> Pathway, Bytewax, Lance, Eland, …). Each tier has its own parallel
> transform set — pirn deliberately does not unify them under a single
> `Frame` interface, because each engine's idioms (lazy expressions,
> push-down, vectorisation) are part of why users pick that engine.
> Tier 1 (`DataBatch`, dict-based) is a fallback for small batches and
> glue, *not* the default. See ARD: **Decision: Tiered Data-Domain
> Architecture (Position B)** for the full tier model and engine roster.


### Problem

ETL/ELT pipelines are pirn's most natural fit, yet users must reinvent extract/transform/load wiring every time. There is no shared vocabulary for data quality, schema validation, partitioning, or incremental loading.

### User Stories

- As a data engineer, I want a pre-built `SqlSource` so I can connect to a database without writing a Source subclass from scratch.
- As an analytics engineer, I want a `DataQualityGate` so I can assert row counts, null rates, and schema conformance before a transform runs.
- As a pipeline author, I want `Partitioner` and `Merger` knots so I can express fan-out/fan-in over date partitions without writing Aggregator boilerplate.

### Proposed Knots

#### Sources
| Knot | Description | Key Config |
|------|-------------|------------|
| `SqlSource` | Executes a SQL query, returns `pd.DataFrame` or list of dicts | `connection_string`, `query` |
| `FileSource` | Reads CSV/Parquet/JSON from local or S3 path | `uri`, `format` |
| `ApiSource` | HTTP GET with pagination support, returns records | `url`, `headers`, `page_param` |
| `StreamSource` | Pulls a batch from a Kafka/Valkey stream topic | `topic`, `batch_size` |

#### Transforms
| Knot | Description | Key Config |
|------|-------------|------------|
| `Rename` | Column renaming map | `mapping: dict[str, str]` |
| `Cast` | Type coercion per column | `schema: dict[str, type]` |
| `Filter` | Row predicate (expression string or callable) | `predicate` |
| `Deduplicate` | Drop duplicate rows on key columns | `keys: list[str]` |
| `Normalize` | Standardize nulls, whitespace, casing | `rules: NormRules` |
| `Join` | Merge two upstream datasets on key(s) | `on`, `how` |
| `Pivot` / `Unpivot` | Reshape wide↔long | `index`, `columns`, `values` |
| `Aggregate` | Group-by + aggregation expressions | `by`, `aggs` |
| `WindowCalc` | Rolling/expanding window functions | `partition_by`, `order_by`, `func` |

#### Quality / Validation
| Knot | Description | Key Config |
|------|-------------|------------|
| `SchemaValidator` | Asserts column presence and types | `schema: DataSchema` |
| `RowCountGate` | Fails if row count outside bounds | `min_rows`, `max_rows` |
| `NullRateGate` | Fails if null rate exceeds threshold per column | `thresholds: dict[str, float]` |
| `FreshnessGate` | Asserts max age of a timestamp column | `column`, `max_age_hours` |
| `Profiler` | Emits descriptive stats as a side-channel artifact | — |

#### Sinks
| Knot | Description | Key Config |
|------|-------------|------------|
| `SqlSink` | Upsert/insert/replace into a DB table | `connection_string`, `table`, `strategy` |
| `FileSink` | Write CSV/Parquet/JSON | `uri`, `format`, `partition_by` |
| `DataCatalogSink` | Write metadata/stats to a catalog (pluggable) | `catalog_url` |

#### Shared Data Contracts
```python
@dataclass
class DataBatch:
    rows: list[dict]
    schema: DataSchema
    source_uri: str
    fetched_at: datetime

@dataclass
class DataSchema:
    columns: dict[str, type]
    primary_keys: list[str]
    nullable: list[str]

@dataclass
class QualityReport:
    passed: bool
    checks: list[QualityCheck]
    row_count: int
    sampled_at: datetime
```

### Example Pipeline: Incremental ETL

```
SqlSource(orders, incremental watermark)
  → FreshnessGate
  → SchemaValidator
  → Deduplicate(on=["order_id"])
  → Join(users_source, on="user_id")
  → Aggregate(by="region", aggs={"revenue": "sum"})
  → NullRateGate(thresholds={"region": 0.0})
  → SqlSink(analytics_db, table="daily_revenue", strategy="upsert")
```

---

## Domain 2: `pirn.domains.agents` — Agentic Pipelines / Patterns

### Problem

LLM-driven agentic systems require recurring patterns — tool dispatch, memory retrieval, planning loops, reflection, handoffs — that don't map cleanly to simple linear pipelines. Users currently hand-roll these in SubTapestry or LoopSubTapestry without shared contracts.

### User Stories

- As an agent builder, I want a `ToolRouter` knot so I can dispatch to registered tools by name without writing custom Branch logic each time.
- As an agent builder, I want a `MemoryRetriever` knot with a standard memory interface so I can swap backends (in-memory, vector store, Redis) without rewiring the pipeline.
- As an agent builder, I want a `ReflectionCheck` knot so I can loop until a quality threshold is met.

### Proposed Knots

#### Input Processing
| Knot | Description |
|------|-------------|
| `MessageParser` | Parses raw user input into `AgentMessage` (role, content, metadata) |
| `ContextBuilder` | Assembles system prompt + history + injected facts into `AgentContext` |
| `IntentClassifier` | Routes to one of N downstream handlers by intent label |

#### Memory
| Knot | Description | Key Config |
|------|-------------|------------|
| `MemoryWriter` | Writes turn/fact to a memory store | `store: MemoryStore` (protocol) |
| `MemoryRetriever` | Semantic or exact lookup from memory store | `store`, `top_k` |
| `ConversationBuffer` | Sliding-window conversation history management | `max_turns` |

#### Planning & Tool Use
| Knot | Description |
|------|-------------|
| `Planner` | LLM call that produces a `Plan` (list of `ToolCall` steps) |
| `ToolRouter` | Dispatches `ToolCall` to registered `Tool` implementations |
| `ToolExecutor` | Executes a single tool, returns `ToolResult` |
| `ToolResultAggregator` | Merges N `ToolResult`s into unified context for next LLM call |

#### Generation & Output
| Knot | Description |
|------|-------------|
| `LLMCall` | Single inference call (model, messages → completion) — provider-agnostic via protocol |
| `StreamingLLMCall` | Streaming variant; emits tokens as they arrive |
| `OutputParser` | Parses structured output (JSON, XML, pydantic) from raw completion |
| `ResponseFormatter` | Formats final agent response for delivery channel |

#### Control Flow
| Knot | Description | Key Config |
|------|-------------|------------|
| `ReflectionCheck` | Scores output; passes if above threshold, re-queues otherwise | `scorer`, `threshold`, `max_retries` |
| `SafetyCheck` | Content policy check; blocks or flags unsafe content | `policy` |
| `HandoffCheck` | Transfers control to another agent/tapestry by name | `agent_registry` |
| `TerminationCheck` | Ends agentic loop when done signal is detected | `done_predicate` |

#### Shared Data Contracts
```python
@dataclass
class AgentMessage:
    role: str          # "user" | "assistant" | "system" | "tool"
    content: str
    metadata: dict

@dataclass
class AgentContext:
    system_prompt: str
    history: list[AgentMessage]
    injected_facts: list[str]

@dataclass
class Plan:
    steps: list[ToolCall]
    reasoning: str

@dataclass
class ToolCall:
    tool_name: str
    arguments: dict
    call_id: str

@dataclass
class ToolResult:
    call_id: str
    output: Any
    error: str | None

@dataclass
class AgentResponse:
    content: str
    citations: list[str]
    tool_calls_made: list[ToolCall]
    turn_id: str
```

### Example Pipeline: ReAct Agent Loop

```
MessageParser
  → ContextBuilder(memory=MemoryRetriever)
  → SafetyCheck
  → Planner(llm=LLMCall)
  → ToolRouter → [ToolExecutor × N tools]
  → ToolResultAggregator
  → LLMCall(generate final response)
  → ReflectionCheck(scorer=quality_fn, threshold=0.8)
  → ResponseFormatter
  → MemoryWriter
```
(Wrapped in `LoopSubTapestry` for multi-turn)

---

## Domain 3: `pirn.domains.ml` — ML Engineering / Data Science

### Problem

ML pipelines span data prep, feature engineering, training, evaluation, and deployment. These stages are widely understood but tedious to wire correctly — especially tracking artifacts, versioning experiments, and gating on evaluation metrics.

### User Stories

- As an ML engineer, I want `TrainTestSplit` and `CrossValidator` knots so I can express experiment setup without boilerplate.
- As an ML engineer, I want a `MetricGate` so my pipeline fails fast when evaluation metrics don't meet a threshold before any model is registered.
- As a data scientist, I want `FeatureSelector` and `Scaler` knots I can chain declaratively rather than writing sklearn pipelines inside a single function.

### Proposed Knots

#### Data Preparation
| Knot | Description | Key Config |
|------|-------------|------------|
| `DatasetLoader` | Loads a labelled `MLDataset` from path or registry | `uri`, `format`, `label_column` |
| `TrainTestSplit` | Splits into train/val/test `DataSplit` | `test_size`, `val_size`, `stratify`, `seed` |
| `CrossValidator` | Produces N-fold `DataSplit` list for cross-validation | `n_folds`, `strategy`, `seed` |
| `Sampler` | Under/over-sample for class imbalance | `strategy`, `target_ratio` |

#### Feature Engineering
| Knot | Description | Key Config |
|------|-------------|------------|
| `Scaler` | StandardScaler / MinMax / Robust | `method`, `columns` |
| `Encoder` | One-hot, ordinal, target encoding | `method`, `columns` |
| `Imputer` | Fill missing values | `strategy`, `columns` |
| `FeatureSelector` | Filter by variance, correlation, or importances | `method`, `threshold` |
| `EmbeddingExtractor` | Text/image → dense vector via pluggable model | `model`, `columns` |
| `PolynomialFeatures` | Interaction and polynomial terms | `degree`, `columns` |
| `FeatureStore` | Read pre-computed features from a feature store | `store_uri`, `feature_set` |

#### Training
| Knot | Description | Key Config |
|------|-------------|------------|
| `Trainer` | Fits a model on a `DataSplit`; returns `TrainedModel` | `estimator`, `hyperparams` |
| `HyperparamSearch` | Grid/random/Bayesian search over param space | `estimator`, `param_grid`, `strategy`, `n_trials` |
| `EnsembleBuilder` | Combines N `TrainedModel`s via stacking/voting | `method` |

#### Evaluation
| Knot | Description | Key Config |
|------|-------------|------------|
| `Evaluator` | Scores a `TrainedModel` on held-out data; returns `EvalReport` | `metrics: list[str]` |
| `MetricGate` | Fails/blocks if any metric falls outside threshold | `thresholds: dict[str, float]` |
| `FairnessAudit` | Evaluates metric parity across demographic slices | `sensitive_cols`, `metrics` |
| `Explainer` | SHAP/LIME feature importance on a model | `method`, `n_samples` |

#### Deployment
| Knot | Description | Key Config |
|------|-------------|------------|
| `ModelSerializer` | Saves `TrainedModel` to disk/registry in standard format | `uri`, `format` |
| `ModelRegistrar` | Registers model with metadata to an experiment tracker | `tracker_uri`, `experiment_name` |
| `ShadowDeployer` | Routes live traffic to candidate + champion; logs deltas | `champion_uri`, `log_store` |
| `Predictor` | Loads model from registry; runs inference on a `DataBatch` | `model_uri` |

#### Shared Data Contracts
```python
@dataclass
class MLDataset:
    features: Any          # pd.DataFrame or np.ndarray
    labels: Any            # pd.Series or np.ndarray
    feature_names: list[str]
    metadata: dict

@dataclass
class DataSplit:
    train: MLDataset
    val: MLDataset | None
    test: MLDataset
    seed: int
    fold_index: int | None

@dataclass
class TrainedModel:
    estimator: Any          # sklearn-compatible or custom
    feature_names: list[str]
    training_metadata: dict
    artifact_uri: str | None

@dataclass
class EvalReport:
    metrics: dict[str, float]
    confusion_matrix: list[list[int]] | None
    passed_threshold: bool
    evaluated_at: datetime
```

### Example Pipeline: Train → Evaluate → Register

```
DatasetLoader(uri="s3://...", label_column="churn")
  → TrainTestSplit(test_size=0.2, stratify=True)
  → [Scaler, Encoder, Imputer] (parallel feature prep)
  → FeatureSelector(method="importance", threshold=0.01)
  → HyperparamSearch(estimator=XGBoost, n_trials=50)
  → Evaluator(metrics=["auc", "f1", "precision", "recall"])
  → MetricGate(thresholds={"auc": 0.85, "f1": 0.75})
  → FairnessAudit(sensitive_cols=["age_group", "region"])
  → ModelRegistrar(experiment_name="churn-v2")
```

---

## Package Layout

```
pirn/
  domains/
    __init__.py
    data/        # types.py, sources.py, transforms.py, quality.py, sinks.py, specializations/
    agents/      # protocols.py, types.py, input.py, memory.py, planning.py, generation.py, control.py, specializations/
    ml/          # protocols.py, types.py, data_prep.py, features.py, training.py, evaluation.py, deployment.py, specializations/
    connectors/  # protocols.py, databases/, object_storage/, streaming/, saas/, bi_catalog/, observability/
    health/      # types.py, protocols.py, clinical.py, genomics.py, mri.py, eeg_meg.py, wearables.py, pathology.py, trials.py
    signal/      # types.py, spectral.py, filters.py, wavelets.py, adaptive.py, statistical.py, separation.py, nonlinear.py, resampling.py, audio.py
    oilgas/      # types.py, protocols.py, seismic.py, well.py, reservoir.py, production.py, integrity.py, geospatial.py, workflows.py
```

Every domain `__init__.py` runs `KnotRegistry.register(name, factory)` for all knots in that module, enabling YAML composition without per-knot import boilerplate. Each `__init__.py` also raises `ImportError` with a `pip install pirn[<extra>]` hint if the domain's heavy dependencies are missing.

---

## Domain 4: `pirn.domains.connectors` — Cross-cutting Source/Sink Connectors

### Problem

Every domain needs to read from and write to the same set of external systems (Postgres, S3, Kafka, BigQuery, Salesforce, etc.). Without a shared connector layer, each domain re-invents connection management, retry logic, pagination, and credential handling.

### User Stories

- As a pipeline author, I want a registered `PostgresConnector` so I can use it as a Source or Sink in any domain pipeline without writing connection-pool code.
- As a platform engineer, I want connectors to share a `ConnectionConfig` protocol so credentials can come from env vars or a secrets manager via one mechanism.
- As a domain library author, I want to consume connectors as Source/Sink Knots in my SubTapestries without owning the integration code.

### Proposed Knots

50 connectors across 6 categories — see `domain-knot-specializations.md` for full enumeration. Categories:

- **Databases (11):** Postgres, MySQL, SQLite, DuckDB, BigQuery, Snowflake, Redshift, ClickHouse, Databricks, MSSQL, Oracle
- **Object Storage (5):** S3, GCS, Azure Blob, local filesystem, HDFS
- **File Formats (7):** Parquet, CSV, JSON, Avro, ORC, Delta, Iceberg
- **Streaming (6):** Kafka, Kinesis, PubSub, RabbitMQ, Azure Service Bus, Valkey Streams
- **SaaS APIs (11):** Salesforce, HubSpot, Stripe, GitHub, Jira, Shopify, Google Analytics, Mixpanel, Amplitude, Zendesk, Twilio
- **BI / Catalog (6):** dbt Artifacts, Fivetran, Airbyte, DataHub, OpenMetadata, Alation
- **Observability (4):** OpenTelemetry, Datadog, Prometheus, Grafana

### Shared Protocols

```python
class FileFormat(Protocol):
    async def read(self, path: str) -> AsyncIterator[Any]: ...
    async def write(self, path: str, data: Any) -> None: ...

class DatabaseConnectionPool(Protocol):
    async def __aenter__(self) -> Connection: ...
    async def __aexit__(self, *exc): ...

@dataclass
class ConnectionConfig:
    """Per-connector credential dataclass injected from env vars / secrets manager."""
    ...
```

---

## Domain 5: `pirn.domains.health` — Healthcare & Life Sciences

### Problem

Healthcare pipelines span seven distinct modalities (Clinical/EHR, Genomics, MRI, EEG/MEG, Wearables, Pathology, Clinical Trials), each with its own data formats, regulatory burden, and tooling. Building from scratch every time creates compliance risk and reinvents wheels.

### User Stories

- As a clinical data engineer, I want `FHIRPatientIngestor` and `OMOPCDMMapper` so I can normalize EHR data without writing FHIR parsing.
- As a bioinformatician, I want `VariantCaller` and `RNASeqQuantifier` so I can run genomics workflows under pirn's lineage tracking.
- As a neuroscientist, I want `EEGICADecomposer` and `MEGSourceLocalization` so I can build EEG/MEG pipelines that compose with statistical post-processing.
- As a clinical trial statistician, I want `SurvivalAnalysisPipeline` and `EstimandAlignedAnalyzer` so I can produce regulatory-grade analyses.

### Proposed Knots

82 specializations — see `domain-knot-specializations.md`. Categories: Clinical/EHR (18), Genomics (19), MRI (14), EEG/MEG (13), Wearables (6), Pathology (5), Clinical Trials/RWE (7).

### Shared Data Contracts

`ClinicalRecord`, `GenomicsRecord`, `DICOMSeries`, `RawEEG`, `WSITile`, `ClinicalTrialRecord` — PHI fields are flagged in dataclass metadata so downstream sinks can enforce field-level encryption. All knots emit `audit_log` metadata for HIPAA audit trails.

### Standards Coverage

FHIR R4, HL7 v2.x, OMOP CDM v5.4, SNOMED CT, ICD-10-CM/PCS, RxNorm, LOINC, FASTQ/BAM/VCF/GVCF, DICOM, NIfTI, BIDS, FIF/EDF/BrainVision, CDISC SDTM/ADaM, ICH E9(R1).

---

## Domain 6: `pirn.domains.signal` — Digital Signal Processing

### Problem

Signal processing is a foundational layer for many domains (audio, biosignals, vibration analysis, communications, seismic). The same algorithms — FFT, wavelets, IIR/FIR filters, Kalman, ICA — get re-implemented across projects. A canonical knot set lets users compose DSP chains declaratively.

### User Stories

- As an audio engineer, I want `STFTAnalyzer` + `MelSpectrogramExtractor` + `MFCCExtractor` so I can build audio ML feature pipelines.
- As a biosignal analyst, I want `ButterworthFilter` + `WaveletDenoiser` + `LMSAdaptiveFilter` so I can clean ECG/EEG without writing scipy boilerplate.
- As a control systems engineer, I want `KalmanFilter` and `ParticleFilter` so I can build state-estimation pipelines.

### Proposed Knots

84 specializations — see `domain-knot-specializations.md`. Categories: Spectral (11), Filtering (17), Wavelets (8), Adaptive (6), Statistical (7), Source Separation (7), Nonlinear/Chaos (5), Resampling/Sync (7), Audio/Speech (8).

### Shared Data Contracts

`SignalFrame` (samples × channels, sample rate, metadata), `SpectrumFrame`, `WaveletFrame`, `SourceFrame`. All knots preserve `sample_rate` through the chain; frequency-domain knots return `SpectrumFrame`.

---

## Domain 7: `pirn.domains.oilgas` — Oil & Gas

### Problem

Oil & gas operations span seismic interpretation, petrophysics, reservoir engineering, production ops, facilities integrity, and geospatial — each with distinct file formats (SEG-Y, LAS, WITSML, ECLIPSE, PRODML), regulatory standards (API, SPE-PRMS, AER, BOEM), and existing tooling silos. A unified knot library lets users build cross-domain workflows (e.g., seismic-to-well-tie, reserves-from-DCA) under one orchestration framework.

### User Stories

- As a geophysicist, I want `SegyFileIngester` + `HorizonAutoPicker` + `AcousticImpedanceInverter` so I can build seismic interpretation pipelines.
- As a petrophysicist, I want a `WellborePetrophysicsWorkflow` SubTapestry so a LAS file produces an interpreted log suite end-to-end.
- As a production engineer, I want `ScadaHistorianIngester` + `ProductionAllocationEngine` + `Scope1EmissionsReporter` so monthly regulatory reporting is deterministic and auditable.
- As a reservoir engineer, I want `ArpsDeclineCurveFitter` + `ReservesEstimationPipeline` so PRMS/SEC reserves estimates have full lineage.

### Proposed Knots

63 specializations — see `domain-knot-specializations.md`. Categories: Seismic (13), Well (15), Reservoir (9), Production (10), Integrity (6), Geospatial (5), Cross-domain ST workflows (4).

### Standards Coverage

SEG-Y rev 0/1/2, LAS 2.0/3.0, WITSML 2.0, PRODML 2.1, OSDU R3, PPDM 39, ECLIPSE DATA deck, CDISC SDTM/ADaM, SPE-PRMS (2018), API 510/570/1163, ASME B31.8, NACE SP0102, EPA AP-42, IPCC 2019, ISO 14064-1, OGMP 2.0.

---

## Open Questions

1. **Dependency management:** Each domain has distinct heavy deps (pandas, sklearn, anthropic SDK, etc.). Should these be optional extras (`pirn[data]`, `pirn[agents]`, `pirn[ml]`)? Almost certainly yes — needs confirmation.

2. **Provider protocols for agents:** `LLMCall`, `MemoryStore`, `Tool` need protocol definitions, not concrete implementations. Where do these protocols live — in `pirn.domains.agents.protocols` or in pirn core?

3. **Sklearn-compatibility assumption for ML:** Should `Trainer` and `Evaluator` require sklearn-compatible estimators, or should they be fully protocol-driven from the start?

4. **Data contract compatibility across domains:** `DataBatch` (data domain) and `MLDataset` (ML domain) overlap. Should there be a shared `pirn.domains.types` for cross-domain primitives (e.g., tabular records)?

5. **Example pipelines as first-class tests:** Should each domain ship an integration test that runs the example pipeline end-to-end with lightweight stubs?

6. **Naming: `pirn.domains` vs `pirn.contrib`:** `domains` implies these are first-party and curated. `contrib` implies community. Which positioning is right?

---

## Success Metrics

- A new user can build a working domain-specific pipeline from registry-only knots in < 30 minutes
- Each domain has ≥ 1 end-to-end example pipeline that runs in CI
- All domain knots appear in the YAML catalog (accessible via `KnotRegistry`)
- Zero changes required to pirn core

---

## Proposed Sequencing

| Phase | Scope | Rationale |
|-------|-------|-----------|
| 0 | Package infrastructure + `pirn.domains.connectors` priority tier (Postgres/SQLite/DuckDB/S3/local/Kafka/Valkey) | Prerequisite — data and ML integration tests need real backends |
| 1 | `pirn.domains.data` | Highest user demand; most natural fit for pirn's existing examples |
| 2 | Remaining connectors (extended DBs, storage, streaming, SaaS, BI, observability) | Backfill connector surface without blocking domain work |
| 3 | `pirn.domains.agents` | Growing field; existing llm_agent example provides scaffolding |
| 4 | `pirn.domains.ml` | Broadest ML surface; most external deps; benefits from patterns from earlier phases |
| 5 | `pirn.domains.health` | Heavy regulated domain; depends on connectors (FHIR over HTTP) and patterns from data domain |
| 6 | `pirn.domains.signal` | Foundational DSP layer; can run in parallel with health since deps are independent |
| 7 | `pirn.domains.oilgas` | Domain-specific; benefits from connectors (S3/Postgres) and signal (FFT, wavelet) primitives |

Phases 5–7 are independent of each other and may be developed in parallel. Each phase: acceptance test (ATDD example pipeline) → types → protocols → sources/inputs → transforms/processing → gates/control → sinks/outputs → specializations → docs.
