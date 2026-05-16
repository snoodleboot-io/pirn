# User Stories: Domain Knot Specializations (Remaining)

**Status:** Backlog
**Related PRD:** PRD-domain-knot-specializations.md

---

## Data Specializations

### Story: Data — CDC Ingestion
**As a** data engineer
**I want** a pre-built CDC consumer for Debezium-formatted Kafka topics
**So that** I can replicate database changes in near-real-time without writing custom op-routing logic

#### Features
- Feature: Debezium Kafka ingestion
  - Task: implement `CDC_DebeziumConsumer` — reads Kafka topic, parses Debezium `c/u/d/r` envelope, routes inserts/updates/deletes to separate downstream handlers in order

---

### Story: Data — Paginated API Ingestion
**As a** data engineer
**I want** a knot that handles paginated REST API extraction
**So that** I can ingest from any cursor- or offset-paginated API without reimplementing retry and accumulation logic

#### Features
- Feature: REST API paged extraction
  - Task: implement `APIPagedExtract` — calls paginated REST API repeatedly (cursor or offset/limit), accumulates all pages with backoff, yields a single combined dataset

---

### Story: Data — Partitioned Date Range Extraction
**As a** data engineer
**I want** to split large historical extracts into date partitions that can be retried independently
**So that** I can backfill years of data without restarting from scratch on failure

#### Features
- Feature: Partitioned date extraction
  - Task: implement `PartitionedDateRangeExtract` — splits a date range into daily/hourly partitions, extracts each via `LoopSubTapestry`, enables parallelism and partial retries

---

### Story: Data — SCD Type 2 History Tracking
**As a** data warehouse engineer
**I want** a pre-built SCD Type 2 implementation
**So that** I can track full dimension history without writing the lookup/close/insert sequence by hand

#### Features
- Feature: SCD Type 2 row history
  - Task: implement `SCD_Type2_HistoryTracking` — lookup current row, detect changes, close old row (set `valid_to`, `is_current=FALSE`), insert new row with surrogate key
  - Task: implement `SCD_Type2_HashDetect` — Type 2 variant using column hash diff instead of per-column comparison

---

### Story: Data — SCD Types 3, 4, 6, 7
**As a** data warehouse engineer
**I want** implementations of SCD Types 3, 4, 6, and 7
**So that** I can choose the appropriate history strategy for each dimension without custom wiring

#### Features
- Feature: SCD Type 3 (previous value)
  - Task: implement `SCD_Type3_PreviousValue` — adds `{col}_previous` columns, shifts current → previous on change, retains one prior value only
- Feature: SCD Type 4 (mini-dimension)
  - Task: implement `SCD_Type4_MiniDimension` — splits rapidly-changing attributes into a separate mini-dim table with lookup and key update
- Feature: SCD Type 6 (hybrid)
  - Task: implement `SCD_Type6_Hybrid` — combines Type 1 + 2 + 3: full row history, current-value columns on all rows, and previous-value columns simultaneously
- Feature: SCD Type 7 (dual surrogate)
  - Task: implement `SCD_Type7_DualSurrogate` — stores `durable_sk` (stable) and `current_sk` (latest row) on every history row, backfills `current_sk` on prior rows after each change

---

### Story: Data — Data Vault Loading
**As a** data vault architect
**I want** standard Hub, Link, and Satellite loader knots
**So that** I can build a Data Vault without writing insert-only loading logic and hash-diff change detection from scratch

#### Features
- Feature: Hub loading
  - Task: implement `DataVault_HubLoader` — insert-only: loads new business keys into a Hub with hash key, load date, record source; re-running with same keys is a no-op
- Feature: Link loading
  - Task: implement `DataVault_LinkLoader` — insert-only: loads relationship rows into a Link (hash of all business keys + individual hub hashes); no updates ever
- Feature: Satellite loading
  - Task: implement `DataVault_SatelliteLoader` — loads attributes into a Satellite: compares hash diff, inserts only changed rows; tracks `load_date`, `load_end_date`, `hash_diff`, record source

---

## Agents Specializations

### Story: Agents — ReAct Loop Primitives
**As an** agent builder
**I want** pre-built ThoughtScratchpad and ActionParser knots
**So that** I can assemble a ReAct loop without writing context management and output parsing from scratch

#### Features
- Feature: ReAct context management
  - Task: implement `ThoughtScratchpad` — prepends all prior (Thought, Action, Observation) triples into LLM context; truncates oldest entries first on token budget
- Feature: ReAct action parsing
  - Task: implement `ActionParser` — parses raw LLM output into structured `action_name` + `action_input`; returns `FinishAction` sentinel when LLM signals done

---

### Story: Agents — Multi-Agent Patterns
**As an** agent system architect
**I want** orchestrator-worker, parallel specialization, and debate patterns
**So that** I can decompose complex tasks across multiple agents without hand-rolling fan-out and synthesis logic

#### Features
- Feature: Orchestrator-worker decomposition
  - Task: implement `OrchestratorWorker` — orchestrator LLM decomposes task, dispatches to specialist workers via Map or dynamic registration, aggregates and synthesizes results
- Feature: Parallel specialist agents
  - Task: implement `ParallelSpecialization` — routes same input to N specialist agents in parallel, collects via Aggregator, synthesizes with general LLM
- Feature: Adversarial debate
  - Task: implement `AgentDebate` — N LLM personas with opposing priors generate positions, critique each other, judge LLM selects winner after N rounds

---

### Story: Agents — Memory Primitives
**As an** agent builder
**I want** episodic memory writing and working memory management knots
**So that** my agents can maintain state across turns without hand-rolling storage and compression

#### Features
- Feature: Episodic memory
  - Task: implement `EpisodicMemoryWriter` — at turn end, summarizes exchange (intent, key facts, decisions) as structured Episode record to persistent store keyed by session ID
- Feature: Working memory
  - Task: implement `WorkingMemoryManager` — bounded in-process scratchpad; compresses oldest entries via LLM summarization when capacity exceeded

---

### Story: Agents — Human-in-the-Loop
**As an** agent system designer
**I want** an ApprovalGate knot that pauses the pipeline for human review
**So that** high-stakes actions require explicit approval before proceeding

#### Features
- Feature: Human approval gate
  - Task: implement `ApprovalGate` — pauses pipeline, emits approval request (webhook/Slack/email), blocks until approved or rejected, supports timeout with auto-reject

---

### Story: Agents — RAG: Hypothetical Document Embedding
**As an** agent builder
**I want** a HypotheticalDocumentEmbedding knot
**So that** I can improve retrieval recall for sparse or abstract queries by embedding a hypothetical answer rather than the raw query

#### Features
- Feature: HyDE retrieval
  - Task: implement `HypotheticalDocumentEmbedding` — LLM generates a hypothetical answer to the query, embeds that answer for retrieval rather than the query itself

---

### Story: Agents — Document Processing
**As an** agent builder
**I want** a DocumentChunker knot
**So that** I can split documents into retrieval-ready chunks with configurable strategy without writing chunking logic in every pipeline

#### Features
- Feature: Document chunking
  - Task: implement `DocumentChunker` — splits documents into chunks using fixed-size-with-overlap, sentence-boundary, semantic, or hierarchical-by-section strategy; attaches position metadata to each chunk

---

## ML Specializations

### Story: ML — Bayesian Hyperparameter Tuning
**As a** machine learning engineer
**I want** a Bayesian optimization tuner
**So that** I can find good hyperparameters with fewer trials than grid or random search

#### Features
- Feature: Bayesian optimization
  - Task: implement `BayesianOptTuner` — uses Optuna (or equivalent) to run sequential Bayesian optimization over the parameter space; returns best params and all trial scores

---

### Story: ML — Cross-Validation
**As a** machine learning engineer
**I want** standard KFold and StratifiedKFold cross-validation knots
**So that** I can evaluate models robustly without writing fold splitting and result aggregation by hand

#### Features
- Feature: K-fold cross-validation
  - Task: implement `KFoldCrossValidator` — N parallel Trainer + Evaluator runs over K folds, aggregates mean/std of metrics across folds
- Feature: Stratified K-fold cross-validation
  - Task: implement `StratifiedKFoldCrossValidator` — same as KFold but preserves class distribution in each fold; required for imbalanced classification

---

### Story: ML — Transfer Learning
**As a** machine learning engineer
**I want** a feature extraction transfer learning knot
**So that** I can fine-tune pre-trained models by freezing the backbone and training only the head

#### Features
- Feature: Feature extraction fine-tuning
  - Task: implement `FeatureExtractionTransferTrainer` — freezes backbone weights, trains classification/regression head on new dataset, supports configurable unfreeze schedule

---

### Story: ML — Graph Feature Extraction
**As a** machine learning engineer
**I want** a graph feature extraction knot
**So that** I can derive features from graph-structured data using GNN-based embeddings

#### Features
- Feature: GNN feature extraction
  - Task: implement `GraphFeatureExtractor` — extracts node and edge embeddings from graph-structured input using a configurable GNN architecture (PyTorch Geometric backed)

---

### Story: ML — Shadow Mode Deployment
**As a** machine learning engineer
**I want** a shadow mode deployer
**So that** I can run a challenger model in shadow alongside the champion, compare outputs, and validate before promoting

#### Features
- Feature: Shadow mode comparison
  - Task: implement `ShadowModeDeployer` — routes production traffic to both champion and challenger models; challenger predictions are logged but not served; outputs comparison metrics for evaluation

---

## Health Specializations

### Story: Health — Genomics Processing
**As a** bioinformatics engineer
**I want** knots for alignment, variant calling, and RNA-seq quantification
**So that** I can build standard genomics pipelines without assembling raw subprocess calls to BWA/GATK/featureCounts

#### Features
- Feature: Reference genome alignment
  - Task: implement `ReferenceGenomeAligner` — aligns short reads to reference genome (BWA/STAR backed); returns aligned BAM path and alignment statistics
- Feature: Variant calling
  - Task: implement `VariantCaller` — calls SNPs and indels from aligned reads (GATK HaplotypeCaller backed); returns VCF path and call statistics
- Feature: RNA-seq quantification
  - Task: implement `RNASeqQuantifier` — quantifies gene-level expression from aligned reads (featureCounts/HTSeq backed); returns count matrix
- Feature: Single-cell preprocessing
  - Task: implement `SingleCellPreprocessor` — QC filtering, normalization, and dimensionality reduction for scRNA-seq data (Scanpy backed)

---

### Story: Health — Neuroimaging Processing
**As a** neuroimaging researcher
**I want** skull-stripping and atlas registration knots
**So that** I can preprocess structural MRI data for downstream analysis without shelling out to FSL manually

#### Features
- Feature: Brain extraction
  - Task: implement `BrainExtractor` — skull-stripping for structural MRI (FSL BET / ANTs backed); returns brain mask and stripped image path
- Feature: Atlas registration
  - Task: implement `BrainAtlasRegistration` — registers subject brain volume to standard atlas (MNI152); returns transformation matrix and registered image
- Feature: Functional connectivity mapping
  - Task: implement `FunctionalConnectivityMapper` — computes ROI-to-ROI correlation matrix from resting-state fMRI time series
- Feature: Neuroimaging QC
  - Task: implement `NeuroimagingQCReporter` — generates MRIQC-style quality metrics for structural and functional scans

---

### Story: Health — Wearables and Clinical Data
**As a** digital health engineer
**I want** sleep staging, ECG classification, and clinical NLP knots
**So that** I can process wearable and EHR data without writing signal processing and NLP pipelines from scratch

#### Features
- Feature: Wearable sleep staging
  - Task: implement `WearableSleepAnalyzer` — classifies sleep stages from actigraphy and heart rate data (GGIR/YASA backed)
- Feature: ECG arrhythmia classification
  - Task: implement `ECGArrhythmiaClassifier` — R-peak detection and rhythm classification from ECG signal (NeuroKit2 backed)
- Feature: Clinical NLP extraction
  - Task: implement `ClinicalNLPExtractor` — named entity recognition for medications, diagnoses, and procedures from free-text clinical notes
- Feature: FHIR parsing
  - Task: implement `HL7FHIRParser` — parses HL7 FHIR R4 bundles into normalized tabular records suitable for downstream analytics
- Feature: Survival analysis
  - Task: implement `SurvivalAnalysisKnot` — Kaplan-Meier and Cox proportional hazards model fitting with censoring support

---

### Story: Health — Computational Pathology
**As a** computational pathology engineer
**I want** WSI tiling, tissue segmentation, and cell detection knots
**So that** I can build slide analysis pipelines without writing tile extraction and morphology feature logic from scratch

#### Features
- Feature: WSI tiling
  - Task: implement `WholeSlideImageTiler` — tiles whole slide image into overlapping patches at configurable magnification and patch size
- Feature: Tissue segmentation
  - Task: implement `TissueSegmenter` — separates tissue from background in WSI patches using thresholding or learned segmentation
- Feature: Cell detection
  - Task: implement `CellDetector` — detects and counts nuclei/cells in histology images; returns bounding boxes and count per patch
- Feature: Morphological feature extraction
  - Task: implement `PathologyFeatureExtractor` — extracts morphological features (area, eccentricity, texture) from segmented cell regions

---

### Story: Health — Clinical Trials Data
**As a** clinical data manager
**I want** adverse event coding, randomization checking, and analysis population building knots
**So that** I can prepare trial datasets for safety and efficacy analysis without custom ETL for each study

#### Features
- Feature: Adverse event coding
  - Task: implement `AdverseEventCoder` — maps free-text adverse event descriptions to MedDRA/CTCAE standard codes
- Feature: Randomization balance checking
  - Task: implement `RandomizationChecker` — validates treatment assignment balance across stratification factors; flags imbalances
- Feature: Analysis population builder
  - Task: implement `SAFESetBuilder` — builds intent-to-treat, per-protocol, and safety analysis populations from raw trial enrollment and disposition data

---

## Signal Specializations

### Story: Signal — Spectral Estimation
**As a** signal processing engineer
**I want** standard PSD estimators (Welch, multitaper) and subspace methods (MUSIC, PISARENKO)
**So that** I can estimate power spectra and resolve closely-spaced frequencies without implementing these algorithms from scratch

#### Features
- Feature: Welch PSD estimation
  - Task: implement `WelchPSDEstimator` — averaged periodogram using Welch's method with configurable window, overlap, and FFT length (SciPy backed)
- Feature: Multitaper PSD estimation
  - Task: implement `MultitaperPSDEstimator` — reduces spectral leakage via DPSS tapers; preferred for short, noisy signals (NiTime/MNE backed)
- Feature: MUSIC frequency estimation
  - Task: implement `MUSICAlgorithm` — subspace method for super-resolution frequency estimation; returns spatial spectrum and frequency estimates
- Feature: PISARENKO frequency estimation
  - Task: implement `PISARENKOAlgorithm` — eigendecomposition-based frequency estimator for sinusoids in white noise; returns frequency and power estimates

---

### Story: Signal — Time-Frequency Analysis
**As a** signal processing engineer
**I want** STFT, CWT, and recurrence plot knots
**So that** I can analyze nonstationary signals in the time-frequency domain without custom spectrogram wiring

#### Features
- Feature: Short-time Fourier transform
  - Task: implement `STFTAnalyzer` — STFT with configurable window function, hop length, and FFT length; returns complex spectrogram and time/frequency axes
- Feature: Continuous wavelet transform
  - Task: implement `CWTAnalyzer` — CWT with configurable mother wavelet and scale range; returns scalogram with adaptive time-frequency resolution
- Feature: Recurrence plot analysis
  - Task: implement `RecurrencePlotAnalyzer` — computes recurrence matrix from phase-space reconstruction; returns recurrence plot and quantification measures (RQA)

---

### Story: Signal — Digital Filtering
**As a** signal processing engineer
**I want** zero-phase and causal IIR/FIR filter knots
**So that** I can apply standard filters without choosing between SciPy's filtfilt and lfilter directly

#### Features
- Feature: Zero-phase filtering
  - Task: implement `FiltFiltFilter` — applies a digital filter forward and backward (zero-phase, SciPy `filtfilt` backed); accepts filter coefficients and padding mode
- Feature: Causal filtering
  - Task: implement `LFilterFilter` — applies a digital filter causally (SciPy `lfilter` backed); lower latency than `filtfilt`, suitable for real-time processing

---

### Story: Signal — Subspace and Cepstral Methods
**As a** signal processing engineer
**I want** ESPRIT and cepstral analysis knots
**So that** I can resolve closely-spaced frequencies and extract pitch/formant information without implementing rotational invariance decompositions from scratch

#### Features
- Feature: ESPRIT frequency estimation
  - Task: implement `ESPRITAlgorithm` — rotational invariance subspace method; more accurate than MUSIC for closely-spaced frequencies; returns complex frequency estimates
- Feature: Cepstral analysis
  - Task: implement `CepstralAnalyzer` — computes real or complex cepstrum with configurable liftering; used for pitch detection and formant extraction

---

## OilGas Specializations

### Story: OilGas — Production Forecasting
**As a** reservoir engineer
**I want** an Arps decline curve fitting knot
**So that** I can fit hyperbolic, exponential, and harmonic decline models to production data without implementing curve fitting from scratch

#### Features
- Feature: Arps decline curve fitting
  - Task: implement `ArpsDeclineCurveFitter` — fits Arps decline models (hyperbolic, exponential, harmonic) to production time series; returns fitted parameters, EUR estimate, and forecast curve

---

### Story: OilGas — Reservoir Data Parsing
**As a** reservoir engineer
**I want** knots for parsing PVT tables and simulator output files
**So that** I can ingest lab reports and simulation results into pirn pipelines without custom file parsers

#### Features
- Feature: PVT table parsing
  - Task: implement `PvtTableParser` — parses and validates PVT tables (Bo, Rs, viscosity vs. pressure) from lab report files; returns structured DataBatch with column validation
- Feature: CMG/Eclipse result parsing
  - Task: implement `CmgResultParser` — parses CMG IMEX/GEM and Eclipse simulator output files into structured DataBatch; handles time step iteration and property extraction

---

### Story: OilGas — Well Engineering
**As a** drilling engineer
**I want** knots for trajectory calculation, deviation survey parsing, and PSV test records
**So that** I can process well engineering data without custom parsers for each file format

#### Features
- Feature: Well trajectory calculation
  - Task: implement `WellTrajectoryCalculator` — minimum curvature method trajectory calculation from deviation survey (MD, inclination, azimuth) to Cartesian coordinates (TVD, N, E)
- Feature: Deviation survey parsing
  - Task: implement `DeviationSurveyParser` — parses directional survey files in LAS-style, CSV, and WITSML formats into structured survey records
- Feature: PSV test record parsing
  - Task: implement `PsvTestRecordParser` — parses pressure safety valve test records; extracts set pressure, test date, pass/fail status, and next due date

---

### Story: OilGas — Integrity Management
**As a** pipeline integrity engineer
**I want** a corrosion rate calculator
**So that** I can process coupon and ER probe readings and automatically flag exceedances against threshold limits

#### Features
- Feature: Corrosion rate calculation
  - Task: implement `CorrosionRateCalculator` — calculates corrosion rate from coupon weight loss or electrical resistance probe readings; flags readings that exceed configured threshold in mils per year (MPY)

---

### Story: OilGas — Seismic Interpretation
**As a** geophysicist
**I want** horizon auto-picking and fault detection knots
**So that** I can automate repetitive interpretation tasks in seismic processing pipelines

#### Features
- Feature: Seismic horizon picking
  - Task: implement `HorizonAutoPicker` — semi-automatic seismic horizon picking using seed points and wave-tracking along amplitude or phase; returns picked horizon surface
- Feature: Fault detection
  - Task: implement `FaultDetectionKnot` — detects fault planes in 3D seismic volumes using coherence or similarity attribute computation; returns fault probability volume

---

### Story: OilGas — Geospatial
**As a** geospatial data engineer
**I want** well header geocoding and offshore block mapping knots
**So that** I can standardize well location data and assign regulatory block identifiers without custom spatial joins

#### Features
- Feature: Well header geocoding
  - Task: implement `WellHeaderGeocoder` — geocodes well surface location from DLS/UWI legal description or lat/lon to a standardized spatial record with projected coordinates
- Feature: Offshore block mapping
  - Task: implement `OffshoreBlockMapper` — maps well or field coordinates to offshore concession block boundaries via spatial join against a configurable block boundary dataset
