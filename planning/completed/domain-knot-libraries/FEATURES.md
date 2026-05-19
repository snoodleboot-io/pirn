# Features: Domain Knot Libraries

**Status:** Complete — 2026-05-15

---

## Feature: Data Domain (~100 knots)

Tiered ELT pipeline knots covering dict transforms through distributed lazy evaluation, with quality, lakehouse, SCD, incremental, and medallion patterns.

### Story: Data engineers can build Tier 1 dict-based pipelines without engine dependencies

#### Tasks
- Implement `DataBatch` type with schema metadata and typed accessors
- Implement Tier 1 dict transform knots (`FilterRows`, `RenameColumns`, `CastTypes`, `AddComputedColumn`, `PivotRows`, `UnpivotColumns`)
- Implement `NullRateCheck`, `RowCountCheck`, `SchemaValidator`, `FreshnessCheck` quality knots
- Implement `DataProfiler` profiling knot

### Story: Data engineers can run frame-native transforms in Polars, Pandas, DuckDB, and DataFusion

#### Tasks
- Implement Tier 2 Polars knots (`PolarsFilter`, `PolarsGroupBy`, `PolarsJoin`, `PolarsSelect`, `PolarsSortBy`, `PolarsWithColumn`)
- Implement `PandasDataBatch` and corresponding Tier 2 Pandas knots
- Implement DuckDB and DataFusion Tier 2 knots with push-down query support
- Implement Tier 2.5 out-of-core knots (Vaex, Modin)

### Story: Data engineers can push computation to remote engines with Ibis, Spark, Ray, and Dask

#### Tasks
- Implement Tier 3 Ibis knots with lazy expression graph (first Tier 3 engine)
- Implement PySpark, Ray Data, and Dask Tier 3 knots
- Implement Tier 3-stream streaming knots (Pathway, Bytewax)
- Implement Tier 4 specialized knots (Lance, Eland)

### Story: Data engineers can apply SCD, incremental, and medallion patterns

#### Tasks
- Implement SCD Type 1, Type 2, Type 3 SubTapestry specializations (`SCDType1Merge`, `SCDType2Upsert`, `SCDType3Current`)
- Implement incremental load knots (`WatermarkSource`, `IncrementalFilter`, `CheckpointSink`)
- Implement medallion layer SubTapestry specializations (`BronzeLayer`, `SilverLayer`, `GoldLayer`)
- Implement data vault knots (`HubLoader`, `SatelliteLoader`, `LinkLoader`)
- Implement dimensional modeling knots (`DimLoader`, `FactLoader`, `BridgeTableLoader`)
- Implement analytics engineering knots (`MetricAggregator`, `DeduplicationKnot`, `SchemaVersionMigrator`)
- Implement feature engineering SubTapestry and ingestion patterns

---

## Feature: Agents Domain (~175 knots)

LLM pipeline knots covering generation, memory, tool use, multi-agent coordination, and safety.

### Story: Agent pipeline authors can call LLMs and manage conversation state

#### Tasks
- Implement `LLMProviderKnot` base and provider-specific subclasses
- Implement `MemoryStoreKnot` and `MemoryStore` base with retrieval knots
- Implement generation knots: `PromptBuilder`, `StreamingLLMSource`, `StructuredOutputParser`
- Implement input/output processing knots (`TokenCounter`, `ContextWindowTrimmer`, `MessageFormatter`)

### Story: Agent pipeline authors can compose ReAct, RAG, and planning loops

#### Tasks
- Implement `ReActLoop` LoopSubTapestry specialization
- Implement RAG SubTapestry (`DocumentRetriever`, `ChunkEmbedder`, `RetrievalAugmentedGenerator`)
- Implement planning SubTapestry (`GoalDecomposer`, `PlanExecutor`, `PlanRefinement`)
- Implement chain-of-thought SubTapestry and reflection knots

### Story: Agent pipeline authors can route tools and enforce guardrails

#### Tasks
- Implement `ToolRouter`, `ToolDecorator`, and tool-calling knots
- Implement guardrail knots (`ContentPolicyCheck`, `OutputValidatorCheck`, `PiiRedactorKnot`)
- Implement human-in-the-loop knots (`ApprovalGate`, `HumanFeedbackSource`)
- Implement multi-agent knots (`AgentDispatcher`, `AgentCollector`, `AgentBroadcast`)
- Implement specialized agent SubTapestry types (`DocumentProcessingAgent`, `ConversationAgent`)

### Story: `LoopSubTapestry` iterates inner tapestries until a termination condition

#### Tasks
- Refactor `LoopSubTapestry` to conform to SubTapestry contract (`_run_inner()` pattern)
- Implement max-iterations guard and done-signal termination
- Propagate per-iteration run metadata (iteration index in run history)
- Publish agentic-loops contributor guide (`docs/contributing/agentic-loops.md`)

---

## Feature: ML Domain (~147 knots)

ML pipeline knots covering data preparation, feature engineering, training, evaluation, and deployment.

### Story: ML engineers can prepare data and engineer features for training

#### Tasks
- Implement data prep knots (`TrainTestSplitter`, `Scaler`, `Imputer`, `Encoder`, `Resampler`)
- Implement feature engineering knots (`FeatureSelector`, `PolynomialFeatures`, `FeatureHasher`, `TargetEncoder`)
- Implement embedding knots via `EmbeddingProvider` abstract interface

### Story: ML engineers can train and evaluate models with fairness audits

#### Tasks
- Implement training knots (`SklearnTrainer`, `XGBoostTrainer`, `LightGBMTrainer`, `PyTorchTrainer`)
- Implement evaluation knots (`ClassificationEvaluator`, `RegressionEvaluator`, `FairnessAudit`)
- Implement SHAP explainability knots (`ShapExplainer`, `ShapPlotter`, `ShapFeatureImportance`)

### Story: ML engineers can deploy, monitor, and shadow-test models

#### Tasks
- Implement `ModelRegistrar` and `Predictor` deployment knots
- Implement `ShadowDeployer` for parallel shadow deployment comparison
- Implement monitoring knots (`PredictionDriftCheck`, `DataDriftCheck`, `ModelPerformanceMonitor`)
- Leave `lineage_store.py`, `embedding_provider.py`, `image_encoder_provider.py`, `feature_store_provider.py` as abstract interfaces (intentional — user responsibility)

---

## Feature: Health Domain (~129 knots)

Health informatics knots covering EEG/MEG, MRI, genomics, clinical, wearables, pathology, and trials — with real MNE, nibabel, and scipy computation.

### Story: Researchers can process EEG/MEG data with MNE-based knots

#### Tasks
- Implement EEG/MEG source knots (`EEGFileSource`, `MEGFileSource`, `BIDSDatasetSource`)
- Implement signal processing knots (`EpochExtractor`, `ArtifactRejecter`, `ICADecomposer`, `SourceLocalizer`)
- Implement assemblers/disassemblers for MNE Raw and Epochs types

### Story: Researchers can process MRI data with NIfTI/DICOM knots

#### Tasks
- Implement MRI source knots (`NIfTISource`, `DICOMSource`, `DICOMSeriesAssembler`)
- Implement neuroimaging processing knots (`BrainMaskApplier`, `SpatialNormalizer`, `GLMFitter`)

### Story: Clinicians can process FHIR R4 and OMOP CDM records

#### Tasks
- Implement FHIR R4 assembler/disassembler for clinical records
- Implement clinical EHR knots (`PatientCohortFilter`, `ObservationAggregator`, `LabResultNormalizer`)
- Implement genomics knots (`VCFSource`, `VariantAnnotator`, `GeneExpressionNormalizer`)
- Implement wearables, pathology, and clinical trials knots

---

## Feature: Signal Domain (~85 knots)

Signal processing knots with real scipy/numpy/librosa/pywt/padasip computation.

### Story: Signal engineers can filter, transform, and analyze signals

#### Tasks
- Implement IIR filter knots (`ButterworthFilter`, `ChebyshevFilter`, `EllipticFilter`)
- Implement FIR filter knots (`FIRWindowFilter`, `FIRLSFilter`, `FIRParksMcClellan`)
- Implement adaptive filter knots (`NLMSFilter`, `RLSFilter`, `KalmanFilter`) via padasip
- Implement nonlinear filter knots (`MedianFilter`, `BilateralFilter`, `SavitzkyGolayFilter`)
- Implement spectral knots (`FFTKnot`, `STFTKnot`, `WelchPSD`, `MTMSpectrum`)
- Implement wavelet knots (`CWTKnot`, `DWTKnot`, `WaveletDenoiser`) via pywt
- Implement audio knots (`MFCCExtractor`, `MelSpectrogramKnot`, `PitchEstimator`) via librosa
- Implement beamforming, resampling, separation, and statistical knots

---

## Feature: OilGas Domain (~109 knots)

Upstream oil and gas knots with real segyio, lasio, and resfo computation.

### Story: Geoscientists can interpret seismic data with segyio-backed knots

#### Tasks
- Implement SEG-Y source knots (`SEGYSource`, `SEGYAssembler`) via segyio
- Implement seismic interpretation knots (`HorizonPicker`, `FaultExtractor`, `AmplitudeExtractor`, `VelocityAnalyzer`)

### Story: Petroleum engineers can process well logs and reservoir models

#### Tasks
- Implement LAS file source knots (`LASSource`, `LASAssembler`) via lasio
- Implement petrophysics knots (`ShaliniessVolumeCalculator`, `WaterSaturationKnot`, `PorosityKnot`)
- Implement reservoir simulation knots (`EclipseResultSource`, `CMGResultSource`) via resfo
- Implement production ops, facilities integrity, and geospatial knots

---

## Feature: Connectors Domain (~265 files)

80+ connector backends spanning relational DBs, cloud storage, streaming, document/graph/time-series, SaaS, BI/catalog, and observability.

### Story: Engineers can connect to relational databases and data warehouses

#### Tasks
- Implement Postgres pool and knots (`PostgresConfig`, `PostgresPool`, `DatabaseQuerySource`, `DatabaseExecuteSink`)
- Implement MySQL, MSSQL, Oracle, ClickHouse configs and pools
- Implement BigQuery, Databricks, DuckDB, Dremio, Snowflake configs and pools

### Story: Engineers can read and write object storage

#### Tasks
- Implement S3, GCS, Azure Blob, HDFS, and local filesystem store configs
- Implement `ObjectStoreReadSource`, `ObjectStoreWriteSink`, `ObjectStoreListSource`

### Story: Engineers can publish and consume from message brokers

#### Tasks
- Implement Kafka, PubSub, Kinesis, RabbitMQ, Azure Service Bus, Valkey broker configs
- Implement `MessageBrokerPublishSink` and `MessageBrokerKnot`

### Story: Engineers can connect to SaaS APIs and BI/catalog tools

#### Tasks
- Implement SaaS client configs (Salesforce, HubSpot, Stripe, GitHub, Jira, Shopify, Twilio, Zendesk, Mixpanel, Amplitude, Airtable, Google Analytics)
- Implement BI/catalog client configs (dbt artifacts, Airbyte, Fivetran, DataHub, Alation, OpenMetadata)
- Implement observability/messaging client configs (PagerDuty, Slack, Teams, Discord, Telegram, Google Chat)

### Story: Engineers can connect to document, graph, and time-series databases

#### Tasks
- Implement document DB configs (MongoDB, ArangoDB, CosmosDB, Couchbase, CouchDB, Firestore)
- Implement graph DB configs (Neo4j, Memgraph, OrientDB)
- Implement time-series DB configs (InfluxDB, TimescaleDB, QuestDB, VictoriaMetrics, kdb+)

---

## Feature: Payload[M, D] Generic Base

Typed, auditable, serialisation-safe base class for all domain payload types.

### Story: All domain payload types share a typed base that transport and audit code can program against

#### Tasks
- Implement `Payload[M, D]` in `pirn/core/payload.py` extending `PirnOpaqueValue`
- Expose `.metadata` and `.data` generic accessors
- Implement `_pirn_audit_dict()` delegating to `metadata._pirn_audit_dict()`
- Implement `PickleSerializer` fallback in `SerializerRegistry` for opaque value transport
- Implement domain-specific `Payload` subclasses with semantic property aliases (`SignalPayload`, `ScadaPayload`, `TrainedModelPayload`, etc.)
- Run payload pattern audit against agents, data, and connectors; fix all violations

---

## Feature: Optional Extras Packaging

Per-domain optional extras so users install only the dependencies they need.

### Story: Users install only the domain libraries they need without dependency conflicts

#### Tasks
- Define per-domain extras in `pyproject.toml` (`pirn[data]`, `pirn[agents]`, `pirn[ml]`, `pirn[health]`, `pirn[signal]`, `pirn[oilgas]`, `pirn[connectors]`)
- Define `pirn[all]` convenience extra for development and CI
- Implement `extras_loader.py` in `pirn/domains/` for guarded import logic
- Add `ImportError` with install hint to each domain `__init__.py`
- Add optional-dependency skip guards to test files that require domain extras (159 files patched)
