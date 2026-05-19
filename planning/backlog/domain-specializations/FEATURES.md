# Features: Domain Knot Specializations

**Status:** Backlog

---

## Feature: Data Domain — Cross-Tier Bridge Knots

Knots that convert between adjacent tier types so engineers can compose multi-tier pipelines without hand-rolling conversion glue.

### Story: Engineers can bridge DataBatch and Polars frames in a single knot

#### Tasks
- Implement `DataBatchToPolarsKnot` — converts `DataBatch` (dict-based) to `polars.DataFrame`, preserving schema metadata as Polars schema
- Implement `PolarsToDataBatchKnot` — converts `polars.DataFrame` back to `DataBatch` with inferred schema

### Story: Engineers can bridge Polars and PyArrow in a single knot

#### Tasks
- Implement `PolarsToArrowKnot` — wraps `polars.DataFrame.to_arrow()`, emits `pyarrow.Table`
- Implement `ArrowToPolarsKnot` — wraps `polars.from_arrow()`, emits `polars.DataFrame`

### Story: Engineers can bridge DataBatch and Pandas frames

#### Tasks
- Implement `DataBatchToPandasKnot` — converts `DataBatch` to `pandas.DataFrame`
- Implement `PandasToDataBatchKnot` — converts `pandas.DataFrame` to `DataBatch` with schema inference

---

## Feature: Agents Domain — Domain-Specific Task Pipelines

End-to-end agent SubTapestry pipelines for the three most common practitioner tasks.

### Story: Agent authors can compose a code generation pipeline

#### Tasks
- Implement `CodeGenerationPipeline` SubTapestry — sequences intent parsing, context retrieval, code synthesis, and syntax validation
- Implement `CodeSyntaxValidatorKnot` — runs AST parse on generated code; emits structured error on failure
- Implement `CodeContextRetrieverKnot` — retrieves relevant code snippets from a memory store given a task description

### Story: Agent authors can compose a document Q&A pipeline

#### Tasks
- Implement `DocumentQAPipeline` SubTapestry — sequences document chunking, embedding, retrieval, and answer generation
- Implement `AnswerGrounderKnot` — verifies answer is supported by retrieved passages (citation check)
- Implement `DocumentChunkRouter` — routes query to the correct document subset based on metadata filters

### Story: Agent authors can compose a data analysis agent pipeline

#### Tasks
- Implement `DataAnalysisAgentPipeline` SubTapestry — sequences schema inference, hypothesis generation, query execution, and interpretation
- Implement `SchemaInferenceLLMKnot` — calls LLM with DataBatch schema to suggest analysis hypotheses
- Implement `QueryInterpretationKnot` — translates natural-language query to SQL/filter spec; returns structured query plan

---

## Feature: ML Domain — Concrete Feature Store Implementation

A concrete in-process feature store so `FeatureStoreReader` and `FeatureStoreWriter` are usable without external infrastructure.

### Story: ML engineers can use an in-process feature store for development and testing

#### Tasks
- Implement `InMemoryFeatureStore` — concrete `FeatureStoreProvider` backed by a dict; supports `get_features()`, `write_features()`, `list_feature_groups()`
- Implement `InMemoryFeatureStoreReader` — concrete `_FeatureStoreReaderKnot` using `InMemoryFeatureStore`
- Implement `InMemoryFeatureStoreWriter` — concrete `FeatureStoreWriter` using `InMemoryFeatureStore`
- Update `feature_store_reader.py` and `feature_store_writer.py` to wire `InMemoryFeatureStore` as the default for testing

### Story: ML engineers can back the feature store with a Parquet filesystem for persistence

#### Tasks
- Implement `ParquetFeatureStore` — concrete `FeatureStoreProvider` backed by a local or S3 Parquet store via `pyarrow.parquet`
- Implement `ParquetFeatureStoreReader` and `ParquetFeatureStoreWriter` specializations

---

## Feature: Health Domain — OMOP CDM Mapper

OMOP standard vocabulary mapping that was blocked on vocabulary database availability.

### Story: Researchers can map clinical concepts to OMOP CDM standard vocabulary

#### Tasks
- Implement `OmopConceptMapper` — maps source codes (ICD-10, SNOMED, LOINC) to OMOP concept IDs; backed by `OmopConnection` protocol
- Implement `OmopConceptMappingKnot` — wraps `OmopConceptMapper` as a pirn Knot
- Implement `InMemoryOmopVocabularyFixture` — minimal bundled vocabulary fixture covering ICD-10 → OMOP for a small test domain; used when no live DB is configured
- Add `@pytest.mark.requires_omop_db` skip guard to live-vocabulary tests; fixture-backed tests run in default suite

### Story: Lab instrument data can be ingested via the `LabInstrumentConnection` protocol

#### Tasks
- Implement `HL7v2LabInstrumentConnection` — concrete `LabInstrumentConnection` backed by HL7 v2 MLLP parsing (via `hl7apy` or stdlib)
- Implement `HL7v2MessageAssembler` — assembles `ClinicalRecord` payload from HL7 v2 ORU^R01 messages

---

## Feature: Signal Domain — Communication System Specializations

Frequency-domain patterns for communications and signal classification.

### Story: Signal engineers can demodulate OFDM signals

#### Tasks
- Implement `OFDMDemodulator` — performs FFT-based OFDM demodulation via numpy/scipy; yields per-subcarrier symbol batches
- Implement `CyclicPrefixRemover` — strips cyclic prefix before FFT window; configurable CP length
- Implement `ChannelEqualizer` — applies least-squares channel estimation and equalization per OFDM symbol

### Story: Signal engineers can apply matched filter detection

#### Tasks
- Implement `MatchedFilterDetector` — cross-correlates received signal with reference template via scipy; emits detection events with SNR
- Implement `DetectionThresholdCheck` — applies CFAR or fixed threshold to matched filter output; passes detections above threshold

### Story: Signal engineers can run a composed spectral estimation pipeline

#### Tasks
- Implement `SpectralEstimationPipeline` SubTapestry — sequences `ARModelEstimator` → `MUSICEstimator` → `EspritEstimator` for high-resolution frequency estimation
- Implement `FrequencyClassifierKnot` — maps estimated frequency peaks to signal class labels given a reference dictionary

---

## Feature: OilGas Domain — Workflow Completion Tails

The four workflow SubTapestries need export, reporting, and handoff knots to be usable end-to-end.

### Story: Geoscientists can export seismic-to-well tie results

#### Tasks
- Implement `SeismicToWellTieReportExporter` — serialises well-tie QC metrics to structured report (JSON + PDF summary via reportlab or fpdf2)
- Implement `WellTieResultSink` — writes well-tie correlated sections back to SEG-Y via segyio
- Wire both into `SeismicToWellTieWorkflow` as terminal steps

### Story: Petroleum engineers can export wellbore petrophysics results

#### Tasks
- Implement `PetrophysicsReportKnot` — assembles LAS output with computed curves (Sw, Vsh, porosity) via lasio
- Implement `WellborePetrophysicsResultSink` — writes updated LAS file to object storage

### Story: Production engineers can export reserves and field production reports

#### Tasks
- Implement `DeclineCurveReportKnot` — serialises EUR estimates and decline parameters to CSV + JSON
- Implement `FieldProductionReportSink` — writes production summary to configurable output (local filesystem or object store)
- Implement `ReservesExportKnot` — formats reserves estimate for handoff to external reservoir reporting systems (PRMS-aligned JSON schema)
