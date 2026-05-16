# Features: Assembler / Disassembler Pattern

---

## Feature: Core Assembler / Disassembler Base Classes

Thin marker base classes in `pirn/core/` that classify knots as assemblers or disassemblers without adding behaviour. Enables type-checker enforcement and code review tooling.

### Story: Domain knot authors can extend Assembler or Disassembler without boilerplate

As a domain knot author, I can extend `Assembler` or `Disassembler` instead of `Knot` directly so that the classification is visible at a glance and enforced structurally.

#### Tasks

- Implement `pirn/core/assembler.py` — `Assembler(Knot)` marker base class
- Implement `pirn/core/disassembler.py` — `Disassembler(Knot)` marker base class
- Write `docs/contributing/assembler-disassembler-pattern.md` — convention document covering definitions, folder locations, naming convention, exemptions (ETL atomic units), and before/after example for `AudioFileIngestor`

---

## Feature: Signal Domain Assemblers and Disassemblers

Bridge knots for the signal domain covering audio ingestion from object stores and egress of processed signal, spectrum, and wavelet payloads.

### Story: Signal pipeline authors can assemble a SignalPayload from raw bytes without I/O

As a signal pipeline author, I can wire `ObjectStoreReadSource → SignalObjectStoreAssembler` so that signal ingestion is testable in-process with no file system access.

#### Tasks

- Create `pirn/domains/signal/assemblers/__init__.py`
- Implement `pirn/domains/signal/assemblers/signal_object_store_assembler.py` — `SignalObjectStoreAssembler(body: bytes, signal_id: str, ...) → SignalPayload`
- Delete `pirn/domains/signal/audio/audio_file_ingestor.py`

### Story: Signal pipeline authors can disassemble processed payloads to raw bytes for object store sinks

As a signal pipeline author, I can wire a disassembler before `ObjectStoreWriteSink` so that processed signal, spectrum, and wavelet results are persisted without I/O in the disassembler.

#### Tasks

- Create `pirn/domains/signal/disassemblers/__init__.py`
- Implement `pirn/domains/signal/disassemblers/signal_object_store_disassembler.py` — `SignalObjectStoreDisassembler(payload: SignalPayload) → bytes`
- Implement `pirn/domains/signal/disassemblers/spectrum_object_store_disassembler.py` — `SpectrumObjectStoreDisassembler(payload: SpectrumPayload) → bytes`
- Implement `pirn/domains/signal/disassemblers/wavelet_object_store_disassembler.py` — `WaveletObjectStoreDisassembler(payload: WaveletPayload) → bytes`

---

## Feature: Oilgas Domain Assemblers and Disassemblers

Bridge knots for the oilgas domain covering LAS, SEG-Y, SCADA, mud log, and well completion ingestion from object stores and databases, and egress of enriched LAS and seismic volumes.

### Story: Oilgas pipeline authors can assemble domain payloads from raw bytes or database rows without I/O

As an oilgas pipeline author, I can wire connector knots to the appropriate assembler so that LAS, SEG-Y, SCADA, mud log, and well completion ingestion is testable in-process.

#### Tasks

- Create `pirn/domains/oilgas/assemblers/__init__.py`
- Implement `pirn/domains/oilgas/assemblers/las_object_store_assembler.py` — `LasObjectStoreAssembler(body: bytes, well_id: str, curves, depth_unit) → LASPayload`
- Implement `pirn/domains/oilgas/assemblers/segy_object_store_assembler.py` — `SegyObjectStoreAssembler(body: bytes, volume_id: str) → SegyVolume`
- Implement `pirn/domains/oilgas/assemblers/scada_database_assembler.py` — `ScadaDatabaseAssembler(rows: list[tuple], tag: str, since: datetime, sample_interval_sec: float) → ScadaPayload`
- Implement `pirn/domains/oilgas/assemblers/mud_log_assembler.py` — `MudLogAssembler(body: bytes) → dict[str, Any]`
- Implement `pirn/domains/oilgas/assemblers/well_completion_object_store_assembler.py` — `WellCompletionObjectStoreAssembler(body: bytes, well_id: str) → DrillingParameters`
- Delete `pirn/domains/oilgas/well/las_file_ingester.py`
- Delete `pirn/domains/oilgas/seismic/segy_file_ingester.py`
- Delete `pirn/domains/oilgas/production/scada_historian_ingester.py`
- Delete `pirn/domains/oilgas/well/mud_logging_ingester.py`
- Delete `pirn/domains/oilgas/well/well_completion_ingester.py`

### Story: Oilgas pipeline authors can disassemble enriched payloads to raw bytes for object store sinks

As an oilgas pipeline author, I can wire a disassembler before `ObjectStoreWriteSink` so that enriched LAS files and processed seismic volumes are persisted without I/O in the disassembler.

#### Tasks

- Create `pirn/domains/oilgas/disassemblers/__init__.py`
- Implement `pirn/domains/oilgas/disassemblers/las_object_store_disassembler.py` — `LasObjectStoreDisassembler(payload: LASPayload) → bytes`
- Implement `pirn/domains/oilgas/disassemblers/segy_object_store_disassembler.py` — `SegyObjectStoreDisassembler(payload: SegyVolume) → bytes`

---

## Feature: Health Domain Assemblers and Disassemblers

Bridge knots for the health domain covering EEG, MEG, DICOM, WSI, and FHIR ingestion from object stores and PACS systems, and egress of processed neuroimaging, imaging, and pathology payloads.

### Story: Health pipeline authors can assemble domain payloads from raw bytes or records without I/O

As a health pipeline author, I can wire connector knots to the appropriate assembler so that EEG, MEG, DICOM, WSI, and FHIR ingestion is testable in-process.

#### Tasks

- Create `pirn/domains/health/assemblers/__init__.py`
- Implement `pirn/domains/health/assemblers/eeg_object_store_assembler.py` — `EegObjectStoreAssembler(body: bytes, subject_id: str, ...) → SignalPayload`
- Implement `pirn/domains/health/assemblers/meg_object_store_assembler.py` — `MegObjectStoreAssembler(body: bytes, signal_id: str, ...) → SignalPayload`
- Implement `pirn/domains/health/assemblers/dicom_pacs_assembler.py` — `DicomPacsAssembler(series: DICOMSeries, staging_dir: str) → DICOMPayload`
- Implement `pirn/domains/health/assemblers/wsi_object_store_assembler.py` — `WsiObjectStoreAssembler(body: bytes, slide_id: str, ...) → tuple[WSITilePayload, ...]`
- Implement `pirn/domains/health/assemblers/fhir_patient_assembler.py` — `FhirPatientAssembler(records: list[dict], ...) → tuple[ClinicalRecord, ...]`
- Delete `pirn/domains/health/eeg_meg/eeg_raw_ingestor.py`
- Delete `pirn/domains/health/eeg_meg/meg_raw_ingestor.py`
- Delete `pirn/domains/health/mri/dicom_ingestor.py`
- Delete `pirn/domains/health/pathology/wsi_tile_extractor.py`
- Delete `pirn/domains/health/clinical/fhir_patient_ingestor.py`

### Story: Health pipeline authors can disassemble processed payloads to raw bytes for archival

As a health pipeline author, I can wire a disassembler before `ObjectStoreWriteSink` so that filtered, epoched, or annotated neuroimaging and pathology results are persisted without I/O in the disassembler.

#### Tasks

- Create `pirn/domains/health/disassemblers/__init__.py`
- Implement `pirn/domains/health/disassemblers/eeg_object_store_disassembler.py` — `EegObjectStoreDisassembler(payload: SignalPayload) → bytes`
- Implement `pirn/domains/health/disassemblers/meg_object_store_disassembler.py` — `MegObjectStoreDisassembler(payload: SignalPayload) → bytes`
- Implement `pirn/domains/health/disassemblers/dicom_object_store_disassembler.py` — `DicomObjectStoreDisassembler(payload: DICOMPayload) → bytes`
- Implement `pirn/domains/health/disassemblers/wsi_object_store_disassembler.py` — `WsiObjectStoreDisassembler(payload: WSITilePayload) → bytes`

---

## Feature: ML Domain Assemblers and Disassemblers

Bridge knots for the ml domain covering model loading from object stores and egress of trained models, datasets, data splits, and eval reports.

### Story: ML pipeline authors can load a TrainedModelPayload from raw bytes without in-process I/O

As an ML pipeline author, I can wire `ObjectStoreReadSource → TrainedModelObjectStoreAssembler` so that model loading for inference is testable in-process.

#### Tasks

- Create `pirn/domains/ml/assemblers/__init__.py`
- Implement `pirn/domains/ml/assemblers/trained_model_object_store_assembler.py` — `TrainedModelObjectStoreAssembler(body: bytes, manifest: ModelManifest) → TrainedModelPayload`

### Story: ML pipeline authors can disassemble ML payloads to raw bytes or rows for persistence

As an ML pipeline author, I can wire a disassembler before a connector sink so that trained models, datasets, data splits, and eval reports are persisted without I/O in the disassembler.

#### Tasks

- Create `pirn/domains/ml/disassemblers/__init__.py`
- Implement `pirn/domains/ml/disassemblers/trained_model_object_store_disassembler.py` — `TrainedModelObjectStoreDisassembler(payload: TrainedModelPayload) → bytes`
- Implement `pirn/domains/ml/disassemblers/dataset_object_store_disassembler.py` — `DatasetObjectStoreDisassembler(payload: DatasetPayload) → bytes`
- Implement `pirn/domains/ml/disassemblers/data_split_object_store_disassembler.py` — `DataSplitObjectStoreDisassembler(payload: DataSplitPayload) → bytes`
- Implement `pirn/domains/ml/disassemblers/eval_report_database_disassembler.py` — `EvalReportDatabaseDisassembler(payload: EvalReportPayload) → list[tuple]`
