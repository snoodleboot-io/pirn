# Execution Plan: Domain Knot Libraries

**Status:** Active  
**Date:** 2026-04-30  
**Branch:** feat/domain-knot-libraries  
**Related:** domain-knot-libraries-prd.md, domain-knot-libraries-ard.md, domain-knot-specializations.md

---

## Block 0 — Planning Finalization

- [x] Update PRD to add Domain 4 (connectors), 5 (health), 6 (signal), 7 (oilgas) summaries and proposed knot tables
- [x] Update ARD: add health/signal/oilgas optional extras to `pyproject.toml` matrix
- [x] Update ARD: extend Implementation Order with Phases 4–6
- [x] Update ARD: add domain-specific packaging notes (heavy deps — pydicom, MNE-Python, segyio, lasio)
- [x] Update ARD: drop the separate `pirn-connectors` package — connectors live under `pirn/domains/connectors/`

---

## Block 1 — Package Infrastructure

- [x] Create `pirn/domains/__init__.py` (top-level domains namespace)
- [x] Add domain optional-dependencies to `pyproject.toml`: `data`, `agents`, `ml`, `health`, `signal`, `oilgas`
- [x] Add per-connector optional-dependencies to the same `pyproject.toml`: `postgres`, `mysql`, `bigquery`, `snowflake`, `duckdb`, `clickhouse`, `databricks`, `mssql`, `oracle`, `s3`, `gcs`, `azure`, `kafka`, `kinesis`, `pubsub`, `rabbitmq`, `azure-servicebus`, `salesforce`, `hubspot`, `stripe`, `github`, `jira`, `shopify`, `otel`, `datadog`, `prometheus`
- [x] Add convenience groups: `all-db`, `all-storage`, `all-stream`, `all-saas`, `all-observability`, `all-domains`, `all`
- [x] Create `pirn/domains/_extras.py` helper (`require_extra()` raises `ImportError` listing missing modules with install hint)
- [x] Each domain `__init__.py` calls `require_extra()` so missing deps surface as actionable errors
- [x] Unit tests: `tests/unit/test_domains_extras.py` (12 tests, all green) — covers helper + per-domain guards + always-clean namespace/agents/connectors imports
- [x] CI: `domain-extras-matrix` job (6 domains) verifies each extra installs in isolation
- [x] CI: `connector-extras-matrix` job (26 connectors) verifies each connector extra installs in isolation
- [x] CI: feed both matrix jobs into `build-feature` and `build-release` `needs:` chains

---

## Block 2 — `pirn.domains.connectors` (prerequisite for data + ML integration tests)

### Protocols & shared infrastructure
- [x] `pirn/domains/connectors/protocols.py` — `DatabaseConnectionPool`, `ObjectStore`, `MessageBroker`, `FileFormat` runtime-checkable Protocols
- [x] `pirn/domains/connectors/_config.py` — `ConnectionConfig` base + `@connection_config` decorator + `scrub_dsn()` helper (DSN/query-string credential redaction)
- [x] Tests: 12 protocol-conformance + 24 ConnectionConfig redaction tests (incl. `__repr__`/`str`/`f-string`/`caplog`/`to_audit_dict()` no-leak coverage)

### Databases — Priority tier (needed for Phase 3 integration tests)
- [x] `connectors/databases/sqlite.py` — `SQLitePool` (`aiosqlite`) — 11 tests incl. injection resistance + parameterized-query enforcement
- [x] `connectors/databases/duckdb.py` — `DuckDBPool` (`duckdb`) — 9 tests incl. read-only mode + injection resistance
- [x] `connectors/databases/postgres.py` — `PostgresPool` (`asyncpg`) — 17 tests with stub asyncpg pool incl. connect-error DSN scrubbing

### Object Storage — Priority tier
- [x] `connectors/object_storage/local.py` — `LocalFilesystemStore` — 21 tests incl. path-traversal rejection (NUL bytes, `..`, absolute paths)
- [x] `connectors/object_storage/s3.py` — `S3Store` (`aioboto3`) — 15 tests with stub boto client incl. key validation + secret redaction

### Streaming — Priority tier
- [x] `connectors/streaming/kafka.py` — `KafkaBroker` (`aiokafka`) — 12 tests with stub producer/consumer
- [x] `connectors/streaming/valkey.py` — `ValkeyStreamBroker` (`valkey`) — 13 tests with stub client (XADD/XREADGROUP/XACK roundtrip)

**Priority tier total:** 7 connectors, 134 unit tests, all green. 327 total unit tests pass with no regressions.

### Databases — Extended tier
- [ ] `connectors/databases/bigquery.py` — `BigQueryConnector`
- [ ] `connectors/databases/snowflake.py` — `SnowflakeConnector`
- [ ] `connectors/databases/redshift.py` — `RedshiftConnector`
- [ ] `connectors/databases/clickhouse.py` — `ClickHouseConnector`
- [ ] `connectors/databases/databricks.py` — `DatabricksConnector`
- [ ] `connectors/databases/mysql.py` — `MySQLConnector`
- [ ] `connectors/databases/mssql.py` — `MSSQLConnector`
- [ ] `connectors/databases/oracle.py` — `OracleConnector`

### Object Storage — Extended tier
- [ ] `connectors/object_storage/gcs.py` — `GCSConnector`
- [ ] `connectors/object_storage/azure_blob.py` — `AzureBlobConnector`

### Streaming — Extended tier
- [ ] `connectors/streaming/kinesis.py` — `KinesisConnector`
- [ ] `connectors/streaming/pubsub.py` — `PubSubConnector`
- [ ] `connectors/streaming/rabbitmq.py` — `RabbitMQConnector`
- [ ] `connectors/streaming/azure_servicebus.py` — `AzureServiceBusConnector`

### SaaS APIs
- [ ] `connectors/saas/salesforce.py` — `SalesforceConnector`
- [ ] `connectors/saas/hubspot.py` — `HubSpotConnector`
- [ ] `connectors/saas/stripe.py` — `StripeConnector`
- [ ] `connectors/saas/github.py` — `GitHubConnector`
- [ ] `connectors/saas/jira.py` — `JiraConnector`
- [ ] `connectors/saas/shopify.py` — `ShopifyConnector`
- [ ] `connectors/saas/google_analytics.py` — `GoogleAnalyticsConnector`
- [ ] `connectors/saas/mixpanel.py` — `MixpanelConnector`
- [ ] `connectors/saas/amplitude.py` — `AmplitudeConnector`
- [ ] `connectors/saas/zendesk.py` — `ZendeskConnector`
- [ ] `connectors/saas/twilio.py` — `TwilioConnector`

### BI & Data Catalog
- [ ] `connectors/bi_catalog/dbt_artifacts.py` — `DbtArtifactsConnector`
- [ ] `connectors/bi_catalog/fivetran.py` — `FivetranConnector`
- [ ] `connectors/bi_catalog/airbyte.py` — `AirbyteConnector`
- [ ] `connectors/bi_catalog/datahub.py` — `DataHubConnector`
- [ ] `connectors/bi_catalog/open_metadata.py` — `OpenMetadataConnector`
- [ ] `connectors/bi_catalog/alation.py` — `AlationConnector`

### Observability
- [ ] `connectors/observability/opentelemetry.py` — `OpenTelemetryConnector` (preferred)
- [ ] `connectors/observability/datadog.py` — `DatadogConnector`
- [ ] `connectors/observability/prometheus.py` — `PrometheusConnector`
- [ ] `connectors/observability/grafana.py` — `GrafanaConnector`

### Package wiring
- [ ] `connectors/__init__.py` — KnotRegistry calls for all connectors
- [ ] `tests/connectors/` — unit tests with stub connection pools; integration smoke tests for postgres + s3 + kafka

---

## Block 3 — `pirn.domains.data`

- [ ] `pirn/domains/data/types.py` — `DataBatch`, `DataSchema`, `QualityReport`, `QualityCheck`
- [ ] `pirn/domains/data/sources.py` — `SqlSource`, `FileSource`, `ApiSource`, `StreamSource`
- [ ] `pirn/domains/data/transforms.py` — `Rename`, `Cast`, `Filter`, `Deduplicate`, `Normalize`, `Join`, `Pivot`, `Unpivot`, `Aggregate`, `WindowCalc`
- [ ] `pirn/domains/data/quality.py` — `SchemaValidator`, `RowCountGate`, `NullRateGate`, `FreshnessGate`, `Profiler`
- [ ] `pirn/domains/data/sinks.py` — `SqlSink`, `FileSink`, `DataCatalogSink`
- [ ] `pirn/domains/data/specializations/ingestion.py` — `FullRefreshExtract`, `WatermarkIncrementalExtract`, `AppendOnlyIngest`, `CDC_DebeziumConsumer`, `APIPagedExtract`, `PartitionedDateRangeExtract`
- [ ] `pirn/domains/data/specializations/medallion.py` — `BronzeRawIngest`, `SilverCleanTransform`, `GoldAggregation`
- [ ] `pirn/domains/data/specializations/scd.py` — SCD Types 0–7 (all variants)
- [ ] `pirn/domains/data/specializations/dedup.py` — `ExactDeduplicator`, `FuzzyDeduplicator`, `ProximityDeduplicator`
- [ ] `pirn/domains/data/specializations/time_series.py` — `TimeSeriesResampler`, `LagFeatureGenerator`, `RollingStatsPipeline`, etc.
- [ ] `pirn/domains/data/specializations/quality.py` — `RowCountTrendGate`, `ValueDistributionShiftDetector`, `DataProfiler`, etc.
- [ ] `pirn/domains/data/specializations/feature_engineering.py` — `DerivedColumnGenerator`, `BinningEncoder`, `GeoEnricher`, etc.
- [ ] `pirn/domains/data/specializations/analytics_eng.py` — `DimensionTableLoader`, `FactTableLoader`, `BridgeTableBuilder`, etc.
- [ ] `pirn/domains/data/__init__.py` — imports all modules; `KnotRegistry.register()` for all knots
- [ ] `examples/data_engineering/incremental_etl.py` — full SqlSource → gates → transforms → SqlSink example
- [ ] `tests/domains/data/unit/` — unit tests per module with stub DataBatch inputs
- [ ] `tests/domains/data/integration/` — end-to-end ETL example pipeline against SQLite

---

## Block 4 — `pirn.domains.agents`

- [ ] `pirn/domains/agents/protocols.py` — `LLMProvider`, `MemoryStore`, `Tool`
- [ ] `pirn/domains/agents/types.py` — `AgentMessage`, `AgentContext`, `Plan`, `ToolCall`, `ToolResult`, `AgentResponse`
- [ ] `pirn/domains/agents/input.py` — `MessageParser`, `ContextBuilder`, `IntentClassifier`
- [ ] `pirn/domains/agents/memory.py` — `MemoryWriter`, `MemoryRetriever`, `ConversationBuffer`
- [ ] `pirn/domains/agents/planning.py` — `Planner`, `ToolRouter`, `ToolExecutor`, `ToolResultAggregator`
- [ ] `pirn/domains/agents/generation.py` — `LLMCall`, `StreamingLLMCall`, `OutputParser`, `ResponseFormatter`
- [ ] `pirn/domains/agents/control.py` — `ReflectionGate`, `SafetyGate`, `HandoffGate`, `TerminationGate`
- [ ] `pirn/domains/agents/specializations/react.py` — `ReActLoop`, `ReActStepExecutor`, `ReActTerminationGate`
- [ ] `pirn/domains/agents/specializations/rag.py` — `NaiveRAGPipeline`, `HyDERAGPipeline`, `CorrectiveRAGPipeline`, `GraphRAGPipeline`, etc.
- [ ] `pirn/domains/agents/specializations/memory_patterns.py` — `EpisodicMemoryPipeline`, `SemanticMemoryPipeline`, etc.
- [ ] `pirn/domains/agents/specializations/multi_agent.py` — `OrchestratorAgent`, `ParallelSpecialistFanOut`, `ConsensusAggregator`, `DebateFramework`
- [ ] `pirn/domains/agents/specializations/guardrails.py` — `InputGuardrailGate`, `OutputGuardrailGate`, `FactCheckGate`, `PIIRedactorGate`
- [ ] `pirn/domains/agents/specializations/structured_output.py` — `JsonExtractorPipeline`, `PydanticValidatorPipeline`, etc.
- [ ] `pirn/domains/agents/specializations/document_processing.py` — `DocumentIngestionPipeline`, `DocumentSummarizerPipeline`, etc.
- [ ] `pirn/domains/agents/specializations/specialized_agents.py` — `SQLAgent`, `CodeAgent`, `ResearchAgent`, `DataAnalystAgent`, `BrowserAgent`
- [ ] `pirn/domains/agents/__init__.py` — KnotRegistry calls
- [ ] `examples/react_agent/react_loop.py` — full ReAct agent example with stub LLMProvider
- [ ] `tests/domains/agents/unit/` — protocol stub tests per module
- [ ] `tests/domains/agents/integration/` — ReAct loop smoke test with stub LLM

---

## Block 5 — `pirn.domains.ml`

- [ ] `pirn/domains/ml/protocols.py` — `LineageStore`, `FeatureStoreProvider`, `EmbeddingProvider`, `ImageEncoderProvider`
- [ ] `pirn/domains/ml/types.py` — `MLDataset`, `DataSplit`, `TrainedModel`, `EvalReport`
- [ ] `pirn/domains/ml/data_prep.py` — `DatasetLoader`, `TrainTestSplit`, `CrossValidator`, `Sampler`
- [ ] `pirn/domains/ml/features.py` — `Scaler`, `Encoder`, `Imputer`, `FeatureSelector`, `EmbeddingExtractor`, `PolynomialFeatures`, `FeatureStore`
- [ ] `pirn/domains/ml/training.py` — `Trainer`, `HyperparamSearch`, `EnsembleBuilder`
- [ ] `pirn/domains/ml/evaluation.py` — `Evaluator`, `MetricGate`, `FairnessAudit`, `Explainer`
- [ ] `pirn/domains/ml/deployment.py` — `ModelSerializer`, `ModelRegistrar`, `ShadowDeployer`, `Predictor`
- [ ] `pirn/domains/ml/specializations/experiments.py` — `BaselineEstablisher`, `AblationStudyPipeline`, `ChampionChallengerGate`, cross-validation variants, search tuners
- [ ] `pirn/domains/ml/specializations/feature_engineering.py` — `TargetEncoder`, `LagFeatureGenerator`, `TextEmbeddingExtractor`, `ImageEmbeddingExtractor`, `FeatureStoreReader/Writer`
- [ ] `pirn/domains/ml/specializations/training.py` — `SklearnTrainerPipeline`, `XGBoostTrainerPipeline`, `NeuralNetTrainerPipeline`
- [ ] `pirn/domains/ml/specializations/evaluation.py` — classification/regression/ranking/timeseries eval pipelines, `WalkForwardValidator`, `BiasDetector`
- [ ] `pirn/domains/ml/specializations/production.py` — `FullTrainDeployPipeline`, `ContinuousTrainingPipeline`, `ModelLineageTracker`, A/B test pipelines, drift monitors
- [ ] `pirn/domains/ml/specializations/task_pipelines.py` — `BinaryClassificationPipeline`, `MulticlassClassificationPipeline`, `RegressionPipeline`, `ForecastingPipeline`, `NLPPipeline`, `ComputerVisionPipeline`
- [ ] `pirn/domains/ml/__init__.py` — KnotRegistry calls
- [ ] `examples/ml_training/train_evaluate_register.py` — churn model example with sklearn
- [ ] `tests/domains/ml/unit/`
- [ ] `tests/domains/ml/integration/` — full pipeline with toy sklearn dataset

---

## Block 6 — `pirn.domains.health`

- [ ] `pirn/domains/health/types.py` — `ClinicalRecord`, `GenomicsRecord`, `DICOMSeries`, `RawEEG`, `SignalFrame`, `WSITile`, `ClinicalTrialRecord`
- [ ] `pirn/domains/health/protocols.py` — `FHIRClient`, `PACSSClient`, `OMOPConnection`, `LabInstrumentConnection`
- [ ] `pirn/domains/health/clinical.py` — `FHIRPatientIngestor`, `HL7v2MessageParser`, `OMOPCDMMapper`, `PHIRedactor`, `ICD10CodeValidator`, `SnomedCTNormalizer`, `RxNormNormalizer`, `LOINCMapper`, `ClinicalNLPExtractor`, `MedicationReconciliationPipeline`, `VitalSignsAggregator`, `LabResultNormalizer`, `DiagnosisCodeRollup`, `ClinicalTrialEligibilityFilter`, `PatientCohortBuilder`, `EncounterTimelineAssembler`, `ClinicalDataQualityGate`, `ReadmissionRiskScorer`
- [ ] `pirn/domains/health/genomics.py` — FASTQQualityController through MultiOmicsIntegrator (19 knots)
- [ ] `pirn/domains/health/mri.py` — DICOMIngestor through LesionSegmenter (14 knots)
- [ ] `pirn/domains/health/eeg_meg.py` — EEGRawIngestor through SeizureDetector (13 knots)
- [ ] `pirn/domains/health/wearables.py` — ECGRPeakDetector through SpirometryAnalyzer (6 knots)
- [ ] `pirn/domains/health/pathology.py` — WSITileExtractor through PathologyFeatureExtractor (5 knots)
- [ ] `pirn/domains/health/trials.py` — SDTMDomainValidator through EstimandAlignedAnalyzer (7 knots)
- [ ] `pirn/domains/health/__init__.py` — KnotRegistry calls
- [ ] `examples/health/clinical_cohort_pipeline.py` — FHIR → OMOP → cohort builder example
- [ ] `tests/domains/health/unit/`
- [ ] `tests/domains/health/integration/` — synthetic FHIR bundle smoke test

---

## Block 7 — `pirn.domains.signal`

- [ ] `pirn/domains/signal/types.py` — `SignalFrame`, `SpectrumFrame`, `WaveletFrame`, `SourceFrame`
- [ ] `pirn/domains/signal/spectral.py` — FFTAnalyzer through HilbertTransformer (11 knots)
- [ ] `pirn/domains/signal/filters.py` — ButterworthFilter through PolyphaseDecimator (17 knots)
- [ ] `pirn/domains/signal/wavelets.py` — DWTDecomposer through VMDDecomposer (8 knots)
- [ ] `pirn/domains/signal/adaptive.py` — LMSAdaptiveFilter through KalmanFilter (6 knots)
- [ ] `pirn/domains/signal/statistical.py` — ExtendedKalmanFilter through PisarenkoEstimator (7 knots)
- [ ] `pirn/domains/signal/separation.py` — ICADecomposer through SSADecomposer (7 knots)
- [ ] `pirn/domains/signal/nonlinear.py` — LyapunovExponentEstimator through HurstExponentEstimator (5 knots)
- [ ] `pirn/domains/signal/resampling.py` — RationalResamplerPipeline through StreamingBufferManager (7 knots)
- [ ] `pirn/domains/signal/audio.py` — AudioFileIngestor through MusicInformationRetriever (8 knots)
- [ ] `pirn/domains/signal/__init__.py` — KnotRegistry calls
- [ ] `examples/signal/eeg_artifact_removal.py` — raw EEG → ICA → bandpower example
- [ ] `tests/domains/signal/unit/`
- [ ] `tests/domains/signal/integration/` — synthetic signal smoke test (scipy-generated)

---

## Block 8 — `pirn.domains.oilgas`

- [ ] `pirn/domains/oilgas/types.py` — `SegyVolume`, `SegyTrace`, `ParsedTraceHeader`, `LasFile`, `WellPath3D`, `DeviationSurvey`, `PVTTable`, `ScadaTimeSeries`, `DrillingParameters`, `FormationTop`
- [ ] `pirn/domains/oilgas/protocols.py` — `HistorianConnection`, `SeismicVolumeStore`, `WellDataService`
- [ ] `pirn/domains/oilgas/seismic.py` — SegyFileIngester through SubvolumeExtractor (13 knots)
- [ ] `pirn/domains/oilgas/well.py` — LasFileIngester through WellCompletionIngester (15 knots)
- [ ] `pirn/domains/oilgas/reservoir.py` — EclipseSmspecParser through TypeCurveFitter (9 knots)
- [ ] `pirn/domains/oilgas/production.py` — ScadaHistorianIngester through WaterInjectionTracker (10 knots)
- [ ] `pirn/domains/oilgas/integrity.py` — PigRunDataProcessor through EnergyEfficiencyKpiCalculator (6 knots)
- [ ] `pirn/domains/oilgas/geospatial.py` — WellLocationProjector through BoundaryProximityChecker (5 knots)
- [ ] `pirn/domains/oilgas/workflows.py` — WellborePetrophysicsWorkflow, SeismicToWellTieWorkflow, FieldProductionReportingWorkflow, DeclineCurveReservesWorkflow (4 ST pipelines)
- [ ] `pirn/domains/oilgas/__init__.py` — KnotRegistry calls
- [ ] `examples/oilgas/petrophysics_workflow.py` — LAS → interpreted log suite example (using Volve open dataset)
- [ ] `tests/domains/oilgas/unit/`
- [ ] `tests/domains/oilgas/integration/` — Arps DCA + LAS parse smoke test with open sample files

---

## Block 9 — Documentation & Polish

- [ ] `docs/domains/data.md` — knot reference, config params, example pipeline
- [ ] `docs/domains/agents.md`
- [ ] `docs/domains/ml.md`
- [ ] `docs/domains/health.md`
- [ ] `docs/domains/signal.md`
- [ ] `docs/domains/oilgas.md`
- [ ] `docs/connectors/index.md` — connector matrix (all connectors × Source/Sink/extras)
- [ ] `docs/contributing/domain-knots.md` — style guide: `@knot` vs `SubTapestry`, dataclass contracts, KnotRegistry naming, testing requirements
- [ ] Update `README.md` to mention domain libraries
- [ ] `CHANGELOG.md` entry for domain knot libraries
- [ ] mkdocs nav updated to include all domain docs

---

## Notes

- **Prerequisite chain:** Block 2 (connectors priority tier) must land before Block 3 integration tests can run
- **Independent:** Blocks 4–8 are independent of each other; can be worked in parallel
- **Testing bar:** every block requires both unit tests (protocol stubs) and at least one integration smoke test before the block is considered done
- **Specializations:** each domain block implements both the generic PRD knots and the specializations from the catalog; the specializations/ subdirectory is the natural home for the composed SubTapestry pipelines

## Quality Bars (every knot, every block, every PR)

These bars apply to all domain implementations and have associated tests as part of the acceptance criteria:

- [ ] **Secure** — parameterized queries; no `shell=True`; allowlists at boundaries; constant-time secret compares; TLS for credentialed network I/O
  - Tests: parameterized-query proof; SSRF/path-traversal allowlist coverage; subprocess argv (no shell)
- [ ] **Performant** — connection pools (no per-call connections); streaming over loading; batched writes; no N+1 queries
  - Tests: pool-reuse + cap; streaming memory bound; N+1 regression
- [ ] **Audit logs** — lineage record per Source/Sink/Gate with knot id, target (scrubbed), operation, count, duration, status; HIPAA `audit_log` for health
  - Tests: lineage-shape assertions; gate decision logged with reason; HIPAA audit shape
- [ ] **No leaks** — secrets, tokens, keys, signed URLs, PHI/PII never in logs; connection strings scrubbed; reuse `pirn.../postgres_dsn_scrubbing` pattern
  - Tests: `caplog` sweep proving no sensitive token/PHI string appears; `__repr__` masks credentials
- [ ] **Sanitization at log boundaries** — sensitive dataclass fields redacted in `__repr__`; explicit `to_audit_dict()` for sanctioned audit emission; raw payload logging is opt-in only
  - Tests: redacted-`__repr__` assertions; `to_audit_dict()` field allowlist; opt-in flag required for raw
- [ ] **Fail-loud, never silent** — no bare `except` / `except Exception: pass`; typed pirn exceptions for validation errors; transient vs. data vs. programming errors differentiated
  - Tests: ruff/grep gate forbidding `except: pass`; typed-exception assertions; retry logic only on transient error classes

**Where a bar is not applicable** to a given knot (e.g., a stateless math transform with no I/O) — state that explicitly in the PR description; do not silently skip the bar.

---

## Development Methodology

**TDD (Test-Driven Development)** — all knot implementations follow red → green → refactor:
1. Write a failing unit test that asserts the knot's output contract for the happy path
2. Write the knot implementation to pass it
3. Add edge-case and error-path tests; refactor if needed
4. Integration test last (verifies the knot against a real lightweight backend)

**ATDD (Acceptance Test-Driven Development)** — each domain block starts with acceptance criteria expressed as executable tests before any implementation:
1. Write the acceptance test as an end-to-end example pipeline test (the integration smoke test) — it defines what "done" means for the block
2. The acceptance test drives which knots and data contracts need to exist
3. Use protocol-conforming stubs so the acceptance test can run in CI without live external services
4. Only mark a block's tasks as done once the acceptance test passes in CI
