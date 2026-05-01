# ARD: Domain Knot Library Architecture

**Status:** Draft  
**Date:** 2026-04-30  
**Branch:** feat/domain-knot-libraries  
**Related PRD:** domain-knot-libraries-prd.md  
**Related:** domain-knot-specializations.md

---

## Decision: Package Structure

### Context

We need a home for the domain libraries: data, agents, ml, connectors, health, signal, and oilgas. Options:

| Option | Path | Tradeoffs |
|--------|------|-----------|
| A | `pirn/domains/{domain}/` | First-party, curated; implies maintainer ownership; single repo / single distribution |
| B | `pirn/contrib/{domain}/` | Community-contribution framing; lower bar to add new domains |
| C | Separate packages (`pirn-data`, `pirn-connectors`, etc.) | Maximum isolation; cleanest dep boundaries; harder to discover; multiple distributions |

**Decision: Option A for all domains, including connectors.**

Rationale: All domain libraries — including connectors — are extensions to pirn that ship as part of the same library. Heavy and divergent dependencies are isolated via per-domain optional extras (`pirn[postgres]`, `pirn[snowflake]`, etc.) rather than via package boundaries. Single repo, single distribution, single version — keeps discovery and packaging simple. Domain knots consume connector knots as Source/Sink inputs through KnotRegistry, no special cross-package wiring needed.

---

## Decision: Dependency Isolation via Optional Extras

### Context

- `pirn.domains.data` needs: `pandas`, `pyarrow`, optionally `sqlalchemy`, `boto3`
- `pirn.domains.agents` needs: nothing heavy in core; concrete LLM clients are user-supplied
- `pirn.domains.ml` needs: `numpy`, `pandas`, `scikit-learn`, optionally `xgboost`, `shap`

Adding these to core `pirn` would bloat the base install for users who only want one domain.

**Decision: Optional extras per domain.**

```toml
# pirn — single pyproject.toml, all extras under one project
[project.optional-dependencies]
# domain logic extras
data    = ["pandas>=2.0", "pyarrow>=14.0"]
agents  = []                                 # no heavy deps; providers are user-supplied
ml      = ["numpy>=1.26", "pandas>=2.0", "scikit-learn>=1.4"]
health  = ["pydicom>=2.4", "mne>=1.6", "nibabel>=5.2", "pyfaidx>=0.7"]
signal  = ["scipy>=1.12", "pywavelets>=1.5", "librosa>=0.10"]
oilgas  = ["segyio>=1.9", "lasio>=0.31"]

# connector extras (per backend; consumed by pirn/domains/connectors/)
postgres   = ["asyncpg>=0.29"]
mysql      = ["aiomysql>=0.2"]
bigquery   = ["google-cloud-bigquery>=3.0"]
snowflake  = ["snowflake-connector-python>=3.0"]
redshift   = ["asyncpg>=0.29"]              # uses PostgreSQL wire protocol
duckdb     = ["duckdb>=0.10"]
clickhouse = ["clickhouse-connect>=0.7"]
databricks = ["databricks-sql-connector>=3.0"]
mssql      = ["aioodbc>=0.5"]
oracle     = ["python-oracledb>=2.0"]
s3         = ["aioboto3>=12.0"]
gcs        = ["google-cloud-storage>=2.0", "gcsfs>=2024.0"]
azure-blob = ["azure-storage-blob>=12.0"]
kafka      = ["confluent-kafka>=2.3"]
kinesis    = ["aioboto3>=12.0"]
pubsub     = ["google-cloud-pubsub>=2.0"]
rabbitmq   = ["aio-pika>=9.0"]
azure-servicebus = ["azure-servicebus>=7.0"]
salesforce = ["simple-salesforce>=1.12"]
hubspot    = ["hubspot-api-client>=8.0"]
stripe     = ["stripe>=7.0"]
github     = ["PyGithub>=2.0"]
jira       = ["atlassian-python-api>=3.0"]
otel       = ["opentelemetry-sdk>=1.20", "opentelemetry-exporter-otlp>=1.20"]
datadog    = ["datadog-api-client>=2.0"]

# convenience groups
all-db      = ["pirn[postgres,mysql,bigquery,snowflake,duckdb,clickhouse]"]
all-storage = ["pirn[s3,gcs,azure-blob]"]
all-stream  = ["pirn[kafka,kinesis,pubsub,rabbitmq]"]
all-domains = ["pirn[data,agents,ml,health,signal,oilgas]"]
all         = ["pirn[all-domains,all-db,all-storage,all-stream,salesforce,hubspot,stripe,otel]"]
```

Each domain's `__init__.py` raises `ImportError` with a helpful message if its extras aren't installed:

```python
try:
    import pandas as pd
except ImportError as e:
    raise ImportError("pirn[data] requires pandas. Install with: pip install pirn[data]") from e
```

---

## Decision: KnotRegistry Auto-Registration Pattern

### Context

Domain knots need to be available by name in YAML pipelines without requiring users to manually import each module. Options:

| Option | Mechanism | Tradeoffs |
|--------|-----------|-----------|
| A | Auto-register on `import pirn.domains.data` | Simple; requires explicit import in user code |
| B | Entry points / plugin discovery | Zero-import discovery; complex packaging; overkill now |
| C | pirn core auto-imports known domains if installed | Magic; couples core to domains |

**Decision: Option A — auto-register on import via `__init__.py`.**

Each domain's `__init__.py` contains all `KnotRegistry.register()` calls. Users who want YAML composition import the domain once (or add it to their pipeline's bootstrap):

```python
import pirn.domains.data   # registers all data knots
import pirn.domains.agents # registers all agent knots
```

A future `pirn.domains.auto` module can do lazy discovery via importlib if this becomes friction.

---

## Decision: Protocol-Driven External Dependencies

### Context

Domain knots that call external systems (databases, LLMs, vector stores, model registries) must not hard-code provider implementations. Options:

| Option | Approach |
|--------|----------|
| A | Protocols (structural subtyping) defined in `pirn.domains.{domain}.protocols` |
| B | Abstract base classes in the same location |
| C | No abstraction — require user to subclass each knot |

**Decision: Option A — Python `Protocol` classes.**

Protocols enable structural subtyping (duck typing with type safety). Users wire in their own client objects; knots just call the protocol interface. Example:

```python
# pirn/domains/agents/protocols.py
class LLMProvider(Protocol):
    async def complete(self, messages: list[AgentMessage], **kwargs) -> str: ...

class MemoryStore(Protocol):
    async def write(self, key: str, value: Any) -> None: ...
    async def retrieve(self, query: str, top_k: int) -> list[Any]: ...

class Tool(Protocol):
    name: str
    async def execute(self, arguments: dict) -> ToolResult: ...
```

This means `LLMCall` knot receives an `LLMProvider` config param — the user passes their Anthropic/OpenAI client, which satisfies the protocol structurally.

---

## Decision: Data Contract Placement

### Context

`DataBatch` (data domain) and `MLDataset` (ML domain) both represent tabular data. There's potential overlap. Options:

| Option | Approach |
|--------|----------|
| A | Keep types in their own domain (`pirn.domains.data.types`, `pirn.domains.ml.types`) — no shared module |
| B | Shared `pirn.domains.types` for cross-domain primitives |
| C | ML domain imports and extends data domain types |

**Decision: Option A for now, with a documented extension point.**

ML pipelines often have different semantics (train/val/test splits, labels separate from features). Forcing convergence early creates unnecessary coupling. If a user wants to pipe a `DataBatch` into an ML knot, they write a thin adapter knot. We document this pattern explicitly.

Revisit after Phase 1+2 are implemented and real cross-domain pipelines emerge.

---

## Decision: Knot Implementation Style — Functions vs Classes

### Context

Pirn supports both `@knot`-decorated functions and `Knot` subclasses. Domain knots should pick one default style for consistency.

| Style | When appropriate |
|-------|-----------------|
| `@knot` functions | Stateless transforms; simple I/O; most domain knots |
| `Knot` subclasses | Stateful (hold a connection pool, a loaded model); need `__init__` beyond config |

**Decision: Default to `@knot` functions; use `Knot` subclasses only when state is genuinely needed.**

Stateful cases: `SqlSource` (connection pool), `Trainer` (loaded estimator returned as artifact), `Predictor` (model loaded from registry). All others: `@knot`.

---

## Decision: Testing Strategy

### Context

Domain knots call external systems. Integration tests would require live DBs, LLM APIs, etc. Options:

| Option | Approach |
|--------|----------|
| A | Unit tests only with protocol-conforming stubs |
| B | Integration tests against lightweight local systems (SQLite, local model) |
| C | Contract tests — verify stubs conform to protocols |

**Decision: Option A + B.**

- Unit tests: stubs conforming to protocols; verify knot logic in isolation.
- Integration smoke tests: each domain ships one end-to-end example pipeline that runs in CI using lightweight local providers (SQLite for data, a stub LLM for agents, a tiny sklearn model for ML).
- These integration tests double as the domain example pipelines from the PRD.

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Protocol interfaces are too narrow for real providers | Medium | Ship interfaces with real providers as first users; iterate before freezing |
| Pandas as required dep for both data and ML causes version conflicts | Low | Pin compatible ranges; test against pandas 2.x |
| `KnotRegistry` name collisions across domains | Low | Namespace by domain prefix: `data.sql_source`, `agents.llm_call`, `ml.trainer` |
| Heavy ML deps (xgboost, shap) increase install surface | Medium | Keep base `pirn[ml]` minimal; add `pirn[ml-extras]` for optional heavy deps |
| Domain knots diverge in style as different contributors work on them | Medium | Establish domain knot style guide in `docs/contributing/domain-knots.md` |

---

## Implementation Order

```
Phase 0: pirn.domains.connectors (prerequisite — data and ML phases depend on these)
  1. pirn/domains/connectors/protocols.py   — FileFormat, DatabaseConnectionPool, ConnectionConfig
  2. pirn/domains/connectors/databases/     — Postgres, SQLite, DuckDB (needed for Phase 1 integration tests)
  3. pirn/domains/connectors/object_storage/ — S3, local filesystem
  4. pirn/domains/connectors/streaming/     — Kafka, Valkey (needed for data domain CDC patterns)
  5. Remaining database connectors (BigQuery, Snowflake, Redshift, ClickHouse, Databricks, MySQL, MSSQL, Oracle)
  6. Remaining storage (GCS, Azure Blob, HDFS)
  7. Remaining streaming (Kinesis, PubSub, RabbitMQ, Azure Service Bus)
  8. SaaS connectors (Salesforce, HubSpot, Stripe, GitHub, Jira, Shopify, etc.)
  9. BI/Catalog connectors (DataHub, OpenMetadata, dbt Artifacts, Fivetran, Airbyte, Alation)
  10. Observability connectors (OpenTelemetry, Datadog, Prometheus, Grafana)

Phase 1: pirn.domains.data
  1. pirn/domains/data/types.py        — DataBatch, DataSchema, QualityReport
  2. pirn/domains/data/sources.py      — SqlSource, FileSource, ApiSource
  3. pirn/domains/data/transforms.py   — Rename, Cast, Filter, Deduplicate, Join, Aggregate
  4. pirn/domains/data/quality.py      — SchemaValidator, RowCountGate, NullRateGate, FreshnessGate
  5. pirn/domains/data/sinks.py        — SqlSink, FileSink
  6. pirn/domains/__init__.py + registry calls
  7. examples/data_engineering/        — incremental ETL example pipeline
  8. tests/domains/data/               — unit + integration tests

Phase 2: pirn.domains.agents
  1. pirn/domains/agents/protocols.py  — LLMProvider, MemoryStore, Tool
  2. pirn/domains/agents/types.py      — AgentMessage, AgentContext, Plan, ToolCall, ToolResult
  3. pirn/domains/agents/input.py      — MessageParser, ContextBuilder, IntentClassifier
  4. pirn/domains/agents/memory.py     — MemoryWriter, MemoryRetriever, ConversationBuffer
  5. pirn/domains/agents/planning.py   — Planner, ToolRouter, ToolExecutor, ToolResultAggregator
  6. pirn/domains/agents/generation.py — LLMCall, OutputParser, ResponseFormatter
  7. pirn/domains/agents/control.py    — ReflectionGate, SafetyGate, HandoffGate, TerminationGate
  8. examples/react_agent/             — ReAct loop example
  9. tests/domains/agents/

Phase 3: pirn.domains.ml
  1. pirn/domains/ml/types.py          — MLDataset, DataSplit, TrainedModel, EvalReport
  2. pirn/domains/ml/data_prep.py      — DatasetLoader, TrainTestSplit, CrossValidator, Sampler
  3. pirn/domains/ml/features.py       — Scaler, Encoder, Imputer, FeatureSelector, EmbeddingExtractor
  4. pirn/domains/ml/training.py       — Trainer, HyperparamSearch, EnsembleBuilder
  5. pirn/domains/ml/evaluation.py     — Evaluator, MetricGate, FairnessAudit, Explainer
  6. pirn/domains/ml/deployment.py     — ModelSerializer, ModelRegistrar, Predictor
  7. examples/ml_training/             — train → evaluate → register example
  8. tests/domains/ml/

Phase 4: pirn.domains.health   (independent of phases 5/6)
  1. pirn/domains/health/types.py     — ClinicalRecord, GenomicsRecord, DICOMSeries, RawEEG, WSITile, ClinicalTrialRecord
  2. pirn/domains/health/protocols.py — FHIRClient, PACSSClient, OMOPConnection
  3. pirn/domains/health/clinical.py  — 18 clinical/EHR knots (FHIRPatientIngestor → ReadmissionRiskScorer)
  4. pirn/domains/health/genomics.py  — 19 genomics knots
  5. pirn/domains/health/mri.py       — 14 MRI/neuroimaging knots
  6. pirn/domains/health/eeg_meg.py   — 13 EEG/MEG knots
  7. pirn/domains/health/wearables.py — 6 wearables knots
  8. pirn/domains/health/pathology.py — 5 pathology knots
  9. pirn/domains/health/trials.py    — 7 clinical trials/RWE knots
 10. examples/health/clinical_cohort_pipeline.py
 11. tests/domains/health/

Phase 5: pirn.domains.signal   (independent of phases 4/6)
  1. pirn/domains/signal/types.py      — SignalFrame, SpectrumFrame, WaveletFrame, SourceFrame
  2. pirn/domains/signal/spectral.py   — 11 spectral analysis knots
  3. pirn/domains/signal/filters.py    — 17 filtering knots (IIR/FIR/median/Savitzky-Golay/Wiener)
  4. pirn/domains/signal/wavelets.py   — 8 wavelet knots (DWT/SWT/CWT/EMD/VMD)
  5. pirn/domains/signal/adaptive.py   — 6 adaptive filter knots (LMS/NLMS/RLS/Kalman/ANC)
  6. pirn/domains/signal/statistical.py — 7 EKF/UKF/particle/AR/MUSIC/ESPRIT knots
  7. pirn/domains/signal/separation.py — 7 ICA/PCA/NMF/beamforming knots
  8. pirn/domains/signal/nonlinear.py  — 5 Lyapunov/entropy/recurrence/Hurst knots
  9. pirn/domains/signal/resampling.py — 7 resampling/sync knots
 10. pirn/domains/signal/audio.py      — 8 audio/speech knots
 11. examples/signal/eeg_artifact_removal.py
 12. tests/domains/signal/

Phase 6: pirn.domains.oilgas   (independent of phases 4/5)
  1. pirn/domains/oilgas/types.py     — SegyVolume, LasFile, WellPath3D, PVTTable, ScadaTimeSeries, FormationTop
  2. pirn/domains/oilgas/protocols.py — HistorianConnection, SeismicVolumeStore, WellDataService
  3. pirn/domains/oilgas/seismic.py   — 13 seismic knots
  4. pirn/domains/oilgas/well.py      — 15 well/petrophysics knots
  5. pirn/domains/oilgas/reservoir.py — 9 reservoir engineering knots
  6. pirn/domains/oilgas/production.py — 10 production ops knots
  7. pirn/domains/oilgas/integrity.py — 6 facilities/integrity knots
  8. pirn/domains/oilgas/geospatial.py — 5 GIS knots
  9. pirn/domains/oilgas/workflows.py — 4 cross-domain SubTapestry pipelines
 10. examples/oilgas/petrophysics_workflow.py
 11. tests/domains/oilgas/
```

---

## Decision: Tiered Data-Domain Architecture (Position B)

### Context

Pirn's data domain originally shipped a single `DataBatch` contract: a
``tuple[Mapping[str, Any], ...]`` flowing between Knots. That works for
small batches and pure-Python pipelines but cannot:

- Operate efficiently on medium/large data (no columnar layout, no
  vectorisation, GC-heavy iteration)
- Use GPU acceleration (cuDF)
- Run out-of-core (Vaex, Modin/Dask)
- Distribute across a cluster (PySpark, Ray Data, Dask)
- Push computation down into the engine where the data already lives
  (Ibis, raw SQL, Snowflake/BigQuery/Redshift native execution)
- Stream (Pathway, Bytewax)
- Handle specialized layouts (Xarray for n-dim labelled, Awkward for
  jagged, Lance for ML/realtime, Eland for Elasticsearch)

Three positions were considered:

| Position | Description | Tradeoff |
|----------|-------------|----------|
| A | Pirn is a data engine — re-implement every transform per backend | Massive duplication; reinvents existing tools |
| B | Pirn is a graph orchestrator; the engine does the work | Lots of small library-native wrappers; users pick their engine; pirn captures lineage |
| C | Pirn defines a Frame interface; backends implement it | Cleaner in theory; in practice always chases LCD and loses each engine's distinct power |

### Decision: Position B + parallel transform sets per tier

Pirn is an orchestrator. Knots wrap library-native operations. Different
tiers of the data domain use different engines; transforms are NOT
shared via a unified `Frame` interface — each tier is its own implementation
because each engine's idioms are a feature, not a bug.

**Efficiency mandate.** The platform must perform well even when users
make poor choices. Tier-1 dict knots emit warnings or refuse oversized
inputs; tier-2/3 knots prefer zero-copy bridges (Arrow) when crossing
tier boundaries; documentation actively steers users toward the right
tier for their data size and shape.

### Tier model

| Tier | Contract | Use cases | Engines |
|------|----------|-----------|---------|
| **0** | Foundational columnar / specialized layouts | zero-copy bridge between tiers, scientific/jagged data | PyArrow, Awkward, Xarray |
| **1** | `DataBatch` (`tuple[dict, ...]`) | small batches, fixtures, validation, glue | pure Python (current) |
| **2** | Single-machine native frames | medium data, columnar speed, in-process SQL | Polars (start), Pandas, DuckDB, DataFusion, Datatable |
| **2-GPU** | GPU frames | GPU-accelerated single-machine | cuDF |
| **2.5** | Out-of-core / drop-in distributed | larger-than-memory single machine, transparent scale-out | Vaex, Modin |
| **3** | Push-down expressions / lazy plans | warehouse data, distributed clusters, lazy execution | Ibis (start), PySpark, Ray Data, Dask |
| **3-stream** | Streaming dataflow | continuous, event-driven, watermark-driven | Pathway, Bytewax (and existing Kafka/Valkey connectors as sources/sinks) |
| **4** | Specialized | per-domain native format | Lance (ML/realtime), Eland (Elasticsearch), Xarray (geoscience), Awkward (HEP) |

**Validation as a cross-cutting concern.** Quality knots can plug into:
- Pirn's existing pure-Python validators (Tier 1, already shipped)
- Pandera (Tier 2 on Pandas/Polars)
- Great Expectations (Tier 2/3, broader coverage)

### Package layout

```
pirn/domains/data/
  data_batch.py, data_schema.py, …          # Tier 1 contracts (current)
  transforms/                                 # Tier 1 transforms (current)
  quality/                                    # Tier 1 quality (current)
  frames/
    polars/                                   # Tier 2 — Polars (first)
    pandas/                                   # Tier 2 — Pandas
    duckdb/                                   # Tier 2 — DuckDB in-process
    datafusion/                               # Tier 2 — DataFusion
    pyarrow/                                  # Tier 0/2 — Arrow bridge
    cudf/                                     # Tier 2-GPU — cuDF
    vaex/                                     # Tier 2.5 — Vaex
    modin/                                    # Tier 2.5 — Modin
  lazy/
    ibis/                                     # Tier 3 — Ibis (first)
    spark/                                    # Tier 3 — PySpark
    ray/                                      # Tier 3 — Ray Data
    dask/                                     # Tier 3 — Dask
  streaming/
    pathway/                                  # Tier 3-stream — Pathway
    bytewax/                                  # Tier 3-stream — Bytewax
  specialized/
    lance/                                    # Tier 4 — Lance
    eland/                                    # Tier 4 — Elasticsearch
  validation/
    pandera/                                  # Tier 2 schema-first
    great_expectations/                       # Tier 2/3 broader
```

(`pirn.domains.health.signal.oilgas` continue to use Tier 0 specialized
formats — Xarray for MRI/EEG, Awkward for HEP-style jagged data — they
sit alongside this catalog.)

### First implementations of each tier

To prove the pattern without committing to all engines at once, pick
one engine per tier as the first implementation. The rest follow only
when there's demonstrated user need.

- **Tier 2 first:** Polars. Fast, Rust-backed, expressive lazy API,
  straightforward conversion to/from Arrow.
- **Tier 3 first:** Ibis. Broadest backend coverage, matches the
  orchestrator framing, doesn't lock pirn to any one warehouse.

### Open follow-ups

- Specific knot catalog per tier (Polars Filter, Polars Aggregate,
  Ibis Filter, Ibis GroupByAggregate, …) — to be detailed in
  `domain-knot-specializations.md` updates.
- Cross-tier bridging knots (e.g. `DataBatchToPolars`,
  `PolarsToArrow`) — needed once we have ≥ 2 tiers in flight.
- Validation framework integration shape (does pirn expose pandera
  schemas as a `QualityCheck` source? same for GE?) — design call
  pending the first Tier-2 implementation.
