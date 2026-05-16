# PRD: Domain Knot Specializations (Remaining)

**Status:** Backlog
**Priority:** Next sprint
**Depends on:** feat/domain-gap-remediation-plan (merged)

---

## Problem Statement

The domain knot libraries (`pirn.domains.*`) were designed to ship 469 specializations across seven domains. The assembler/disassembler bridge layer (Phases 1–5) is complete; the generic knot primitives are in place. However, the concrete specializations — the named, composable building blocks that users actually reach for — are largely unimplemented. Without them, users must hand-roll patterns that should already exist.

This PRD tracks what remains across five domains (data, agents, ml, health, signal, oilgas) excluding the connectors domain, which has its own PRD.

---

## Goals

- Ship the missing specializations so users have idiomatic, KnotRegistry-composable building blocks for each domain
- Make each specialization testable in isolation
- Enable example pipelines to be written for each domain category
- Bring all domains to a state where a new user can get a working pipeline without writing custom knots

---

## Scope — What Remains

The catalog (`domain-knot-specializations.md`) documents 469 total specializations. Based on post-implementation audit, approximately 29 data, 10 agents, 6 ML, 20 health, 11 signal, and 11 oilgas specializations remain unimplemented.

---

## Out of Scope

- Connectors domain (tracked separately in `PRD-connectors-infrastructure.md`)
- Generic knot primitives (Source, Sink, Aggregator, Branch, Gate — already implemented in core)
- Changes to the engine or assembler/disassembler layers
- Third-party framework integrations (no dbt wrapper, no LangChain wrapper)

---

## Domain Breakdown

### Domain 1: `pirn.domains.data` — ~29 Missing

The data domain is tiered. Pirn is an orchestrator; engines do the work. The missing specializations span ingestion, SCD patterns, Data Vault loading, and incremental strategies.

**Ingestion & Extraction (3 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `CDC_DebeziumConsumer` | ST | CDC is the most common pattern for low-latency replication; Debezium is the dominant open-source implementation |
| `APIPagedExtract` | ST | REST API ingestion is ubiquitous; pagination handling is always reinvented |
| `PartitionedDateRangeExtract` | ST | Enables parallelism and partial retries for large historical loads |

**Slowly Changing Dimensions (5 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `SCD_Type2_HistoryTracking` | ST | The most commonly used SCD pattern in data warehousing |
| `SCD_Type2_HashDetect` | ST | Hash-based change detection eliminates per-column comparison boilerplate |
| `SCD_Type3_PreviousValue` | K | Lightweight "one prior value" pattern for low-cardinality dimensions |
| `SCD_Type4_MiniDimension` | ST | Separates rapidly-changing attributes to avoid dimension table churn |
| `SCD_Type6_Hybrid` | ST | Combines Type 1+2+3 for warehouses that need current-state views and full history |
| `SCD_Type7_DualSurrogate` | ST | Stable + current surrogate key pattern for complex BI scenarios |

**Data Vault (3 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `DataVault_HubLoader` | K | Insert-only hub loading is the entry point for any Data Vault implementation |
| `DataVault_LinkLoader` | K | Relationship loading with hash key generation |
| `DataVault_SatelliteLoader` | K | Attribute loading with hash-diff change detection |

The remaining data specializations (medallion, dimensional model, quality, deduplication, time series, feature engineering, analytics engineering, schema evolution) have partial or complete implementations; verify against the catalog before starting.

---

### Domain 2: `pirn.domains.agents` — ~10 Missing

The agents domain scaffolding is in place. Missing specializations span agentic pattern nodes that require LLM plumbing or external state.

| Name | Type | Category | Why it matters |
|------|------|----------|----------------|
| `AgentDebate` | ST | Multi-Agent | Adversarial generation pattern for decision quality |
| `ApprovalGate` | K | Human-in-the-Loop | Blocks pipeline until human approval received |
| `DocumentChunker` | K | Document Processing | Foundation of every RAG pipeline |
| `EpisodicMemoryWriter` | K | Memory | Persistent session memory across turns |
| `HypotheticalDocumentEmbedding` | ST | RAG | Improves recall for sparse queries |
| `OrchestratorWorker` | ST | Multi-Agent | Core orchestrator decomposition pattern |
| `ParallelSpecialization` | ST | Multi-Agent | Fan-out to N specialist agents |
| `ThoughtScratchpad` | K | ReAct | Context management for ReAct loops |
| `WorkingMemoryManager` | K | Memory | Bounded scratchpad with LLM compression |
| `ActionParser` | K | ReAct | Parses LLM output into structured action + finish sentinel |

---

### Domain 3: `pirn.domains.ml` — ~6 Missing

The ML domain has most experiment-pattern and preprocessing specializations in place. Missing items are in hyperparameter tuning, cross-validation, transfer learning, and deployment patterns.

| Name | Type | Category | Why it matters |
|------|------|----------|----------------|
| `BayesianOptTuner` | ST | Hyperparameter Tuning | Converges faster than grid/random search; Optuna-backed |
| `KFoldCrossValidator` | ST | Cross-Validation | Standard CV implementation |
| `StratifiedKFoldCrossValidator` | ST | Cross-Validation | Required for imbalanced classification |
| `FeatureExtractionTransferTrainer` | ST | Transfer Learning | Freeze backbone, train head — standard fine-tuning pattern |
| `GraphFeatureExtractor` | K | Feature Engineering | GNN-based feature extraction for graph-structured data |
| `ShadowModeDeployer` | ST | Deployment Patterns | Runs new model in shadow alongside champion; compares outputs without serving shadow predictions |

---

### Domain 4: `pirn.domains.health` — ~20 Missing

The health domain assemblers replaced the deleted ingestors. The gap is in specialized processing knots for genomics, neuroimaging, and clinical data.

**Genomics (4 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `ReferenceGenomeAligner` | K | Aligns short reads to reference (BWA/STAR backed) — entry point for variant and RNA-seq pipelines |
| `VariantCaller` | K | Calls SNPs/indels from aligned reads (GATK HaplotypeCaller backed) |
| `RNASeqQuantifier` | K | Gene-level expression quantification from aligned reads (featureCounts/HTSeq backed) |
| `SingleCellPreprocessor` | ST | QC filtering, normalization, and dimensionality reduction for scRNA-seq (Scanpy backed) |

**Neuroimaging (4 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `BrainExtractor` | K | Skull-stripping for structural MRI (FSL BET / ANTs backed) |
| `BrainAtlasRegistration` | K | Registers subject brain to standard atlas (MNI152) |
| `FunctionalConnectivityMapper` | ST | Computes ROI-to-ROI correlation matrix from resting-state fMRI |
| `NeuroimagingQCReporter` | K | Generates MRIQC-style QC metrics for structural and functional scans |

**Wearables & Clinical (5 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `WearableSleepAnalyzer` | ST | Classifies sleep stages from actigraphy + HR (GGIR/YASA backed) |
| `ECGArrhythmiaClassifier` | K | R-peak detection + rhythm classification (NeuroKit2 backed) |
| `ClinicalNLPExtractor` | ST | Named entity recognition for medications, diagnoses, procedures from clinical notes |
| `HL7FHIRParser` | K | Parses HL7 FHIR R4 bundles into normalized tabular records |
| `SurvivalAnalysisKnot` | K | Kaplan-Meier + Cox PH model fitting with censoring support |

**Pathology (4 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `WholeSlideImageTiler` | K | Tiles WSI into overlapping patches at configurable magnification |
| `TissueSegmenter` | K | Separates tissue from background in WSI patches |
| `CellDetector` | K | Detects and counts nuclei/cells in histology images |
| `PathologyFeatureExtractor` | K | Extracts morphological features (area, eccentricity, texture) from segmented cells |

**Clinical Trials (3 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `AdverseEventCoder` | K | Maps free-text AE descriptions to MedDRA/CTCAE codes |
| `RandomizationChecker` | K | Validates treatment assignment balance across stratification factors |
| `SAFESetBuilder` | ST | Builds safety analysis-ready datasets (ITT, PP, SAF populations) from raw trial data |

---

### Domain 5: `pirn.domains.signal` — ~11 Missing

The signal domain has foundational knots in place. Missing are spectral estimation algorithms, time-frequency analysis, and subspace methods.

**Spectral Estimation (4 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `WelchPSDEstimator` | K | Averaged periodogram — the most widely used PSD estimator |
| `MultitaperPSDEstimator` | K | Reduces spectral leakage via DPSS tapers; preferred for short, noisy signals |
| `MUSICAlgorithm` | K | Subspace method for super-resolution frequency estimation |
| `PISARENKOAlgorithm` | K | Eigendecomposition-based frequency estimator for sinusoids in noise |

**Time-Frequency Analysis (3 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `STFTAnalyzer` | K | Short-time Fourier transform with configurable window; returns spectrogram |
| `CWTAnalyzer` | K | Continuous wavelet transform; time-frequency analysis with adaptive resolution |
| `RecurrencePlotAnalyzer` | K | Visualizes recurrence structure in nonlinear time series |

**Filtering (2 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `FiltFiltFilter` | K | Zero-phase forward-backward filtering (SciPy filtfilt backed) |
| `LFilterFilter` | K | Causal IIR/FIR filtering (SciPy lfilter backed) — lower latency than filtfilt |

**Subspace Methods (2 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `ESPRITAlgorithm` | K | Rotational invariance subspace method; more accurate than MUSIC for closely-spaced frequencies |
| `CepstralAnalyzer` | K | Liftered cepstrum computation for pitch and formant extraction |

---

### Domain 6: `pirn.domains.oilgas` — ~11 Missing

The oilgas domain assemblers replaced deleted ingestors. The gap is in interpretation, engineering calculations, and operations knots.

**Reservoir & Production (3 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `ArpsDeclineCurveFitter` | K | Fits Arps hyperbolic/exponential/harmonic decline models; backbone of production forecasting |
| `PvtTableParser` | K | Parses and validates PVT tables (Bo, Rs, viscosity vs. pressure) from lab reports |
| `CmgResultParser` | K | Parses CMG/Eclipse reservoir simulator output files into structured DataBatch |

**Well Engineering (4 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `WellTrajectoryCalculator` | K | Minimum curvature method trajectory calculation from survey data |
| `DeviationSurveyParser` | K | Parses directional survey files (LAS-style, CSV, WITSML) into structured survey records |
| `PsvTestRecordParser` | K | Parses pressure safety valve test records for integrity management |
| `CorrosionRateCalculator` | K | Calculates corrosion rate from coupon or ER probe readings; flags exceedances |

**Seismic Interpretation (2 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `HorizonAutoPicker` | K | Semi-automatic seismic horizon picking using seed points + wave-tracking |
| `FaultDetectionKnot` | K | Detects fault planes in 3D seismic volumes using coherence/similarity attributes |

**Geospatial (2 missing)**

| Name | Type | Why it matters |
|------|------|----------------|
| `WellHeaderGeocoder` | K | Geocodes well surface location from DLS/UWI or lat/lon to a standardized spatial record |
| `OffshoreBlockMapper` | K | Maps well coordinates to offshore concession block boundaries |

---

## Success Criteria

1. All missing specializations listed above have concrete implementations under `pirn/domains/<domain>/`
2. Each specialization has a corresponding unit test
3. All specializations are registered in the domain's `KnotRegistry`
4. At least one example pipeline per domain category demonstrates composition
5. Optional-dependency imports use the established skip-guard pattern (see `tests/` for reference)
6. The domain catalog document is updated to reflect implementation status

---

## Implementation Notes

- Follow the one-class-per-file rule; each specialization lives in its own module
- SubTapestries are composed from existing generic knots — do not duplicate generic logic
- Heavy dependencies are isolated via optional extras; guard imports with `try/except ImportError`
- Validate against the engineering principles baseline: secure, performant, audited, no leaks, log-sanitized, fail-loud
- Health domain: HIPAA-sensitive data flows through several knots — ensure no PII is logged
- Signal and OilGas domains: numerical stability matters; use established SciPy/NumPy conventions
