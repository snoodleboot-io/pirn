# Assembler / Disassembler Pattern — Implementation Plan

**Created:** 2026-05-10  
**Branch:** feat/domain-gap-remediation-plan  
**Status:** Approved for implementation

---

## Problem Statement

pirn's connector knots produce and consume raw Python types (`bytes`, `list[tuple]`,
`list[str]`, `str` paths). Domain knots produce and consume typed `Payload` subclasses
(`SignalPayload`, `LASPayload`, `ScadaPayload`, etc.). There is no standardised layer
bridging these two worlds, and no convention telling domain authors where or how to
create one.

Currently, ingestor knots collapse the bridge into their own `process()` — accepting
a raw path or connection string and producing a Payload in one step. The ingestor IS
the assembler, just with I/O coupled in. This means:

- Ingestors are untestable without file system or network access
- The I/O concern (reading bytes from an object store) is coupled to the domain concern
  (interpreting those bytes as a `SignalPayload`)
- The connector layer cannot be reused across domains

The ingestor concept is therefore invalid. Ingestors are deleted and replaced by an
assembler knot that receives already-materialised raw data from a connector parent.

---

## Scope

### In scope

- Convention document codifying the Assembler/Disassembler pattern
- Assembler knots for all domain ingestion boundaries (raw connector output → Payload)
- Disassembler knots for all domain egress boundaries (Payload → raw connector input)
- Deletion of ingestor knots that collapse I/O and assembly into one step — the
  assembler is the replacement; there is no separate ingestor concept

### Out of scope

- ETL specialisations in `data/specializations/` that perform atomic read-transform-write
  cycles against database pools (SCD, incremental, analytics engineering, data vault,
  dimensional, medallion, quality, schema migration) — these own their I/O by design
- `FileSource`, `SqlSource`, `DirectorySource` in `data/sources/` — these are already
  the assembler layer for `DataBatch`
- `TuplesToDataBatchKnot` / `DataBatchToTuplesKnot` in `data/specializations/medallion/`
  — these are correct assembler/disassembler knots already; they are the reference
  implementation

---

## Definitions

**Assembler knot** — converts raw connector output into a domain `Payload`.
- Receives raw types: `bytes`, `list[tuple]`, `list[str]`, `dict[str, Any]`
- Produces a `Payload[M, D]` subclass
- Lives in: `pirn/domains/{domain}/assemblers/`
- Naming: `{Subject}{Source}Assembler` — e.g. `SignalObjectStoreAssembler`,
  `LasObjectStoreAssembler`, `ScadaDatabaseAssembler`

**Disassembler knot** — converts a domain `Payload` into raw types for a connector sink.
- Receives a `Payload[M, D]` subclass
- Produces raw types: `bytes`, `list[tuple]`, etc.
- Lives in: `pirn/domains/{domain}/disassemblers/`
- Naming: `{Subject}{Sink}Disassembler` — e.g. `SignalObjectStoreDisassembler`,
  `TrainedModelObjectStoreDisassembler`

**Rule:** Assembler/Disassembler knots are required at every domain boundary where a
domain Payload crosses into or out of raw connector I/O. ETL knots that perform an
atomic read-transform-write cycle against a pool or broker are exempt.

---

## Gap Inventory

### signal domain

| Gap | Ingestor deleted | Replacement assembler |
|-----|-----------------|----------------------|
| Audio file ingestion | `AudioFileIngestor` — deleted | `SignalObjectStoreAssembler(body: bytes, ...) → SignalPayload` |

**Disassemblers required** — processed signal results are written back to object stores:

| Required disassembler | Input | Output | Rationale |
|-----------------------|-------|--------|-----------|
| `SignalObjectStoreDisassembler` | `SignalPayload` | `bytes` | Write filtered/resampled/normalised audio back to object store |
| `SpectrumObjectStoreDisassembler` | `SpectrumPayload` | `bytes` | Persist computed spectra (FFT/STFT results) for downstream consumers |
| `WaveletObjectStoreDisassembler` | `WaveletPayload` | `bytes` | Persist wavelet decomposition results |

---

### oilgas domain

| Gap | Ingestor deleted | Replacement assembler |
|-----|-----------------|----------------------|
| LAS file ingestion | `LasFileIngester` — deleted | `LasObjectStoreAssembler(body: bytes, well_id: str, curves, depth_unit) → LASPayload` |
| SEG-Y file ingestion | `SegyFileIngester` — deleted | `SegyObjectStoreAssembler(body: bytes, volume_id: str) → SegyVolume` |
| SCADA historian ingestion | `ScadaHistorianIngester` — deleted | `ScadaDatabaseAssembler(rows: list[tuple], tag: str, since: datetime, sample_interval_sec: float) → ScadaPayload` |
| Mud log ingestion | `MudLoggingIngester` — deleted | `MudLogAssembler(body: bytes) → dict[str, Any]` |
| Well completion ingestion | `WellCompletionIngester` — deleted | `WellCompletionObjectStoreAssembler(body: bytes, well_id: str) → DrillingParameters` |

**Disassemblers required** — enriched oilgas results need persistence back to object stores:

| Required disassembler | Input | Output | Rationale |
|-----------------------|-------|--------|-----------|
| `LasObjectStoreDisassembler` | `LASPayload` | `bytes` | Write petrophysically-enriched LAS files (new curves added by evaluators) back to object store |
| `SegyObjectStoreDisassembler` | `SegyVolume` | `bytes` | Persist migrated/processed seismic volumes |

---

### health domain

| Gap | Ingestor deleted | Replacement assembler |
|-----|-----------------|----------------------|
| EEG raw ingestion | `EEGRawIngestor` — deleted | `EegObjectStoreAssembler(body: bytes, subject_id: str, ...) → SignalPayload` |
| MEG raw ingestion | `MegRawIngestor` — deleted | `MegObjectStoreAssembler(body: bytes, signal_id: str, ...) → SignalPayload` |
| DICOM ingestion | `DICOMIngestor` — deleted | `DicomPacsAssembler(series: DICOMSeries, staging_dir: str) → DICOMPayload` |
| WSI tile extraction | `WsiTileExtractor` — deleted | `WsiObjectStoreAssembler(body: bytes, slide_id: str, ...) → tuple[WSITilePayload, ...]` |
| FHIR patient ingestion | `FhirPatientIngestor` — deleted | `FhirPatientAssembler(records: list[dict], ...) → tuple[ClinicalRecord, ...]` |

**Disassemblers required** — processed health results need persistence for downstream consumers and archival:

| Required disassembler | Input | Output | Rationale |
|-----------------------|-------|--------|-----------|
| `EegObjectStoreDisassembler` | `SignalPayload` | `bytes` | Write processed (filtered/epoched) EEG signals back to object store |
| `MegObjectStoreDisassembler` | `SignalPayload` | `bytes` | Write processed MEG signals back to object store |
| `DicomObjectStoreDisassembler` | `DICOMPayload` | `bytes` | Write DICOM analysis results (segmentations, annotations) back to PACS/object store |
| `WsiObjectStoreDisassembler` | `WSITilePayload` | `bytes` | Write classified/annotated WSI tiles back to object store |

---

### ml domain

| Gap | Knot today | Required assembler/disassembler |
|-----|-----------|--------------------------------|
| Model registration egress | `ModelRegistrar(serialized: bytes, store: ObjectStore)` — calls `store.put()` inline | `TrainedModelObjectStoreDisassembler(payload: TrainedModelPayload) → bytes` then feed to `ObjectStoreWriteSink` |
| Model loading for prediction | `Predictor(model_id: str, store: ObjectStore)` — loads from store inline | `TrainedModelObjectStoreAssembler(body: bytes, manifest: ModelManifest) → TrainedModelPayload` |
| Dataset egress | No existing knot — gap | `DatasetObjectStoreDisassembler(payload: DatasetPayload) → bytes` — serialise dataset to object store for caching and reproducibility |
| Data split egress | No existing knot — gap | `DataSplitObjectStoreDisassembler(payload: DataSplitPayload) → bytes` — persist train/val/test splits for experiment reproducibility |
| Eval report egress | No existing knot — gap | `EvalReportDatabaseDisassembler(payload: EvalReportPayload) → list[tuple]` — write eval metrics rows to database via `DatabaseExecuteSink` |

---

## Implementation Order

Execute one phase at a time. Do not begin a phase until the prior one is complete and
reviewed.

### Phase 1 — Convention document + base classes

Write `docs/contributing/assembler-disassembler-pattern.md` covering:
- Definition of Assembler and Disassembler
- When each is required vs exempt (ETL atomic units)
- Folder location convention (`assemblers/`, `disassemblers/`)
- Naming convention
- Reference implementation pointer (`TuplesToDataBatchKnot`,
  `DataBatchToTuplesKnot`)
- Example: before/after for `AudioFileIngestor`

Create thin marker base classes in `pirn/core/`:
- `Assembler(Knot)` — marker base; no additional logic; lets tooling, type checkers,
  and humans identify assembler knots at a glance; all assemblers extend this instead
  of `Knot` directly
- `Disassembler(Knot)` — same rationale for disassembler knots

These bases add no behaviour — they exist purely for classification. The `process()`
contract is still enforced by `Knot.__init_subclass__`.

**Files to create:**
- `docs/contributing/assembler-disassembler-pattern.md` ✅
- `pirn/core/assembler.py`
- `pirn/core/disassembler.py`

---

### Phase 2 — signal domain

**Files to create:**
- `pirn/domains/signal/assemblers/__init__.py` ✅
- `pirn/domains/signal/assemblers/signal_object_store_assembler.py` ✅
- `pirn/domains/signal/disassemblers/__init__.py`
- `pirn/domains/signal/disassemblers/signal_object_store_disassembler.py`
- `pirn/domains/signal/disassemblers/spectrum_object_store_disassembler.py`
- `pirn/domains/signal/disassemblers/wavelet_object_store_disassembler.py`

**Files to delete:**
- `pirn/domains/signal/audio/audio_file_ingestor.py` ✅

---

### Phase 3 — oilgas domain

**Files to create:**
- `pirn/domains/oilgas/assemblers/__init__.py`
- `pirn/domains/oilgas/assemblers/las_object_store_assembler.py`
- `pirn/domains/oilgas/assemblers/segy_object_store_assembler.py`
- `pirn/domains/oilgas/assemblers/scada_database_assembler.py`
- `pirn/domains/oilgas/assemblers/mud_log_assembler.py`
- `pirn/domains/oilgas/assemblers/well_completion_object_store_assembler.py`
- `pirn/domains/oilgas/disassemblers/__init__.py`
- `pirn/domains/oilgas/disassemblers/las_object_store_disassembler.py`
- `pirn/domains/oilgas/disassemblers/segy_object_store_disassembler.py`

**Files to delete:**
- `pirn/domains/oilgas/well/las_file_ingester.py`
- `pirn/domains/oilgas/seismic/segy_file_ingester.py`
- `pirn/domains/oilgas/production/scada_historian_ingester.py`
- `pirn/domains/oilgas/well/mud_logging_ingester.py`
- `pirn/domains/oilgas/well/well_completion_ingester.py`

---

### Phase 4 — health domain

**Files to create:**
- `pirn/domains/health/assemblers/__init__.py`
- `pirn/domains/health/assemblers/eeg_object_store_assembler.py`
- `pirn/domains/health/assemblers/meg_object_store_assembler.py`
- `pirn/domains/health/assemblers/dicom_pacs_assembler.py`
- `pirn/domains/health/assemblers/wsi_object_store_assembler.py`
- `pirn/domains/health/assemblers/fhir_patient_assembler.py`
- `pirn/domains/health/disassemblers/__init__.py`
- `pirn/domains/health/disassemblers/eeg_object_store_disassembler.py`
- `pirn/domains/health/disassemblers/meg_object_store_disassembler.py`
- `pirn/domains/health/disassemblers/dicom_object_store_disassembler.py`
- `pirn/domains/health/disassemblers/wsi_object_store_disassembler.py`

**Files to delete:**
- `pirn/domains/health/eeg_meg/eeg_raw_ingestor.py`
- `pirn/domains/health/eeg_meg/meg_raw_ingestor.py`
- `pirn/domains/health/mri/dicom_ingestor.py`
- `pirn/domains/health/pathology/wsi_tile_extractor.py`
- `pirn/domains/health/clinical/fhir_patient_ingestor.py`

---

### Phase 5 — ml domain

**Files to create:**
- `pirn/domains/ml/assemblers/__init__.py`
- `pirn/domains/ml/assemblers/trained_model_object_store_assembler.py`
- `pirn/domains/ml/disassemblers/__init__.py`
- `pirn/domains/ml/disassemblers/trained_model_object_store_disassembler.py`
- `pirn/domains/ml/disassemblers/dataset_object_store_disassembler.py`
- `pirn/domains/ml/disassemblers/data_split_object_store_disassembler.py`
- `pirn/domains/ml/disassemblers/eval_report_database_disassembler.py`

**Files to delete:** _(none — `model_registrar.py` and `predictor.py` are legitimate Sink/domain
knots that own I/O by design; they are not ingestor anti-patterns and were restored after
an incorrect deletion)_

---

## Assembler Contract (all phases)

Every assembler knot must:
1. Extend `Assembler` (from `pirn.core.assembler`) — not `Knot` or `Source` directly
2. Declare `process()` with the raw input types and return a `Payload` subclass
3. Include `**_: Any` in `process()`
4. Raise `TypeError` before `ValueError` when validating inputs
5. Not perform I/O — it receives already-materialised raw values from its connector
   parent knot

Every disassembler knot must:
1. Extend `Disassembler` (from `pirn.core.disassembler`) — not `Knot` directly
2. Declare `process()` accepting a `Payload` subclass and returning raw types
3. Include `**_: Any` in `process()`
4. Raise `TypeError` before `ValueError` when validating inputs
5. Not perform I/O

---

## Tests Required (per phase)

For each assembler/disassembler:
- Unit test: valid input → correct Payload type returned
- Unit test: invalid raw input → correct exception type and message
- Unit test: metadata fields on the Payload are correctly populated from raw input

For each deleted ingestor:
- Remove corresponding test file if it exists
- Confirm no other file imports the deleted ingestor before deleting

---

## Open Questions

None — all decisions made:
- ✅ Naming: `Assembler` / `Disassembler`
- ✅ Location: `assemblers/` / `disassemblers/` within each domain
- ✅ Scope: all connector touch points, ETL atomic units exempt
- ✅ Data domain: no gaps (sources are already the assembler layer)
- ✅ Ingestors: deleted, not refactored — the assembler is the replacement
- ✅ Base classes: thin marker `Assembler(Knot)` and `Disassembler(Knot)` in `pirn/core/`; all implementations extend these
