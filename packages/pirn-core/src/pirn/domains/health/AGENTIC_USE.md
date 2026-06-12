# AGENTIC_USE — pirn.domains.health

> The health domain provides format connectors, orchestration knots, and sub-domain pipelines for healthcare and life-science data (imaging, clinical interoperability, biosignals, genomics, trials, wearables, pathology) — it does NOT supply clinical algorithms, reference databases, or regulatory-submission tooling.

---

## Mental model

The health domain sits on top of the core pirn framework. Every format connector is a `BatchFileFormat` subclass that decodes bytes into sanitised record dicts; every sub-domain knot is a `Knot` subclass whose `process()` method you compose into a `Tapestry`.

**PHI redaction is the layer boundary, not a feature flag.** The decode path of every format that touches Protected Health Information strips or hashes identifiers before any downstream knot can see the record. There is no `redact=False` escape hatch; if you need re-identifiable access you must operate directly against source bytes with your own access controls. The pirn connector layer is not that path.

PHI treatment varies by field type:

| Field type | Treatment |
|---|---|
| Patient / subject primary key | SHA-256 hex digest emitted under a `*_hash` key |
| Name, birth date, address, phone, email | Dropped entirely from decoded records |
| Free-text fields that routinely contain PHI | Dropped entirely |
| HIPAA Safe Harbor quasi-identifiers | Dropped entirely |
| Structured PHI in fixed-width headers (EDF/BDF, BrainVision, HL7 v2, CDA) | Replaced with `"[REDACTED]"` on encode and stripped on decode |

Hashing identifiers (rather than dropping) preserves cohort-level linkage: pipelines can cross-reference patients across runs by comparing hashes without ever materialising raw IDs.

**NIfTI is the only health format without PHI redaction.** NIfTI headers rarely carry patient metadata in standard pipelines, but subject information embedded by some acquisition systems is not stripped. Run source files through `dcm2niix` (which strips identifiers during DICOM-to-NIfTI conversion) before ingestion.

**Lineage verification.** Every knot run emits a `KnotLineage` record accessible via `RunResult.lineage`. To verify that redaction fired, inspect the lineage for the format knot: confirm `patient_id_hash` (not `patient_id`) is present in the output record and that the `metadata` mapping contains no PHI keys.

**Compliance posture.** The format layer enforces HIPAA Safe Harbor de-identification for the fields it knows about. It does NOT enforce HIPAA minimum necessary, GDPR data residency, 21 CFR Part 11, or IRB/consent compliance — those are operational and organisational obligations.

---

## Install

```bash
pip install pirn[health]     # DICOM, FHIR, HL7v2, EDF/EDF+/BDF, BrainVision,
                             # CDA, NIfTI, BIDS, OpenSlide, mzML, Define-XML, SDTM XPT
pip install pirn[genomics]   # FASTA, FASTQ, VCF, BCF connectors only (subset of health)
```

OpenSlide also requires the system C library — the Python binding alone is not enough:

```bash
# Debian / Ubuntu
apt install openslide-tools

# macOS
brew install openslide
```

---

## Source map

```
pirn/domains/health/
├── __init__.py                  ← domain package; heavy SDKs NOT imported at load time
├── clinical/                    ← FHIR / OMOP / clinical NLP / ICD-10 / LOINC / RxNorm
├── mri/                         ← DICOM / NIfTI / volumetrics / radiomic features
├── eeg_meg/                     ← EDF / EDF+ / BDF / BrainVision via mne
├── genomics/                    ← FASTA / FASTQ / VCF / BCF / NGS pipeline knots
├── pathology/                   ← WSI tiles / tissue / cell detection (OpenSlide)
├── trials/                      ← SDTM / ADaM / Define-XML / MedDRA
├── wearables/                   ← ECG / HRV / sleep / glucose / spirometry
├── protocols/                   ← FhirClient, PacsClient, OmopConnection, LabInstrumentConnection
└── types/                       ← shared domain value types

├── assemblers/
│   ├── __init__.py
│   ├── eeg_object_store_assembler.py         — bytes + metadata → SignalPayload (EEG)
│   ├── meg_object_store_assembler.py         — bytes + metadata → SignalPayload (MEG)
│   ├── dicom_pacs_assembler.py               — DICOMSeries + staging_dir → DICOMPayload
│   ├── wsi_object_store_assembler.py         — bytes + slide_id + metadata → tuple[WSITilePayload, ...]
│   └── fhir_patient_assembler.py             — list[dict] + metadata → tuple[ClinicalRecord, ...]
├── disassemblers/
│   ├── __init__.py
│   ├── eeg_object_store_disassembler.py      — SignalPayload → bytes
│   ├── meg_object_store_disassembler.py      — SignalPayload → bytes
│   ├── dicom_object_store_disassembler.py    — DICOMPayload → bytes
│   └── wsi_object_store_disassembler.py      — WSITilePayload → bytes

pirn/domains/connectors/file_formats/
├── dicom_format.py              ← DicomFormat        (pirn[health])
├── fhir_json_format.py          ← FhirJsonFormat     (pirn[health])
├── fhir_xml_format.py           ← FhirXmlFormat      (pirn[health])
├── hl7v2_format.py              ← Hl7v2Format        (pirn[health])
├── edf_format.py                ← EdfFormat          (pirn[health])
├── edf_plus_format.py           ← EdfPlusFormat      (pirn[health])
├── nifti_format.py              ← NiftiFormat        (pirn[health])
└── ...                          ← BdfFormat, BrainVisionFormat, CdaXmlFormat,
                                    DefineXmlFormat, SdtmXptFormat, OpenSlideFormat, MzmlFormat
```

---

## Assembler and Disassembler knots

Domain payloads enter and leave the health domain through assembler/disassembler knots. The ingestor pattern is abolished — no ingestor classes exist.

### Assemblers

| Knot | Input | Output |
|------|-------|--------|
| `EegObjectStoreAssembler` | `bytes` + signal metadata | `SignalPayload` |
| `MegObjectStoreAssembler` | `bytes` + signal metadata | `SignalPayload` |
| `DicomPacsAssembler` | `DICOMSeries` + `staging_dir` | `DICOMPayload` |
| `WsiObjectStoreAssembler` | `bytes` + slide metadata | `tuple[WSITilePayload, ...]` |
| `FhirPatientAssembler` | `list[dict]` + cohort metadata | `tuple[ClinicalRecord, ...]` |

### Disassemblers

| Knot | Input | Output |
|------|-------|--------|
| `EegObjectStoreDisassembler` | `SignalPayload` | `bytes` |
| `MegObjectStoreDisassembler` | `SignalPayload` | `bytes` |
| `DicomObjectStoreDisassembler` | `DICOMPayload` | `bytes` |
| `WsiObjectStoreDisassembler` | `WSITilePayload` | `bytes` |

All extend `Assembler` / `Disassembler` from `pirn.core`. None perform I/O — they transform already-materialised values.

PHI note: PHI stripping happens at the **connector** layer (format decoders), not in assemblers. By the time bytes reach an assembler, PHI has already been redacted.

---

## Format reference

| Format | Class | Required extra | PHI redaction | Notes |
|---|---|---|---|---|
| DICOM | `DicomFormat` | `health` | `PatientID` → `patient_id_hash`; name/DOB/address/comments dropped | Whole-file buffering; pixel data as raw bytes |
| FHIR JSON | `FhirJsonFormat` | `health` | `identifier` → `identifier_hash`; name/birthDate/address/telecom dropped | One record per Bundle entry |
| FHIR XML | `FhirXmlFormat` | `health` | Same as FhirJsonFormat; uses defusedxml + lxml | Same record shape as FhirJsonFormat |
| HL7 v2 | `Hl7v2Format` | `health` | PID fields 3,5,7,11,18,19,20 → `"[REDACTED]"` | One record per MSH segment / message |
| CDA XML | `CdaXmlFormat` | `health` | Patient name/birthTime/addr/telecom → `"[REDACTED]"` | One record per document |
| EDF | `EdfFormat` | `health` | patientname/patientcode/birthdate/admincode stripped; `"[REDACTED]"` on encode | One record per signal channel |
| EDF+ | `EdfPlusFormat` | `health` | Same as EdfFormat; adds annotation record to stream | Subclass of EdfFormat |
| BDF | `BdfFormat` | `health` | Same as EdfFormat | 24-bit BioSemi variant |
| BrainVision | `BrainVisionFormat` | `health` | SubjectName/SubjectID/InstitutionName stripped | Input is a zip of .vhdr/.vmrk/.eeg; falls back to pure-Python parser if mne absent |
| NIfTI | `NiftiFormat` | `health` | None — see Mental model | Uses temp file internally; nibabel requires filesystem path |
| BIDS | `BidsDatasetFormat` | `health` | None | Input is zip of dataset; pybids optional for layout validation |
| OpenSlide (WSI) | `OpenSlideFormat` | `health` + system lib | Vendor-specific patient keys stripped from metadata | Read-only; encode raises NotImplementedError |
| mzML | `MzmlFormat` | `health` | None (no PHI in mass spec data) | One record per spectrum |
| Define-XML | `DefineXmlFormat` | `health` | None (structural metadata only) | One record per ItemDef |
| SDTM XPT | `SdtmXptFormat` | `health` | None (de-identified before submission) | First record carries `_metadata` key |
| FASTA | `FastaFormat` | `genomics` | None | One record per sequence entry |
| FASTQ | `FastqFormat` | `genomics` | None | One record per read |
| VCF | `VcfFormat` | `genomics` | None | One record per variant |
| BCF | `BcfFormat` | `genomics` | None | Binary VCF via pysam |

---

## PHI redaction

Redaction is unconditional on the decode path — there is no parameter to disable it.

**What fires automatically per format:**

- `DicomFormat`: `PatientID` is SHA-256 hashed into `patient_id_hash`. All DICOM tags in the HIPAA Safe Harbor identifier list (patient name, DOB, address, phone/email, age, weight, BMI, comments, ethnic group, occupation, and several more) are dropped from the `metadata` mapping before the record is returned.
- `FhirJsonFormat` / `FhirXmlFormat`: `identifier` is replaced by `identifier_hash` (SHA-256 of the JSON-serialised identifier object). `name`, `birthDate`, `address`, and `telecom` are dropped from each resource.
- `Hl7v2Format`: PID segment fields at 1-based positions 3 (MRN), 5 (name), 7 (DOB), 11 (address), 18 (account number), 19 (SSN), and 20 (driver's license) are replaced with `"[REDACTED]"`. All other segments pass through unmodified.
- `CdaXmlFormat`: Patient `name`, `birthTime`, `addr`, and `telecom` elements are replaced with `"[REDACTED]"`.
- `EdfFormat` / `EdfPlusFormat` / `BdfFormat`: `patientname`, `patientcode`, `birthdate`, and `admincode` header fields are stripped from decoded records. On encode, `pyedflib` setters write `"[REDACTED]"` into those fields. If none of the four setters are available on the installed pyedflib version, `RuntimeError` is raised — encode is rejected rather than silently writing PHI.
- `BrainVisionFormat`: `.vhdr` keys `SubjectName`, `SubjectID`, and `InstitutionName` are stripped from decoded records and replaced with `"[REDACTED]"` on encode.
- `OpenSlideFormat`: Vendor-specific metadata keys (`aperio.Patient`, `aperio.PatientID`, `hamamatsu.Reference`, `leica.Identifier`, `mirax.SLIDE_BARCODE`) are stripped.

**What is NOT scrubbed automatically:**

- Free-text clinical notes or report text embedded in structured fields (e.g. DICOM `ImageComments` if not in the known PHI keyword list, CDA body section text).
- PHI embedded in pixel data, image overlays, or burned-in annotations (common in legacy DICOM).
- NIfTI subject metadata embedded by non-standard acquisition software.
- Any PHI introduced downstream of the format layer (e.g. knots that reconstruct patient names from hashed IDs via external lookups).

**Verify via lineage:**

```python
result = await tapestry.run(run_request)
for lineage in result.lineage:
    if lineage.knot_id == "my_dicom_knot":
        output = lineage.output
        assert "patient_id_hash" in output
        assert "PatientName" not in output.get("metadata", {})
```

---

## Canonical pattern

DICOM decode with PHI redaction, pixel data forwarded to a downstream analysis knot:

```python
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.connectors.file_formats.dicom_format import DicomFormat
from pirn.tapestry import Tapestry
from typing import Any
import numpy as np


class DicomLoader(Knot):
    """Decodes raw DICOM bytes; emits one sanitised record."""

    async def process(self, raw_bytes: bytes, **_: Any) -> dict[str, Any]:
        fmt = DicomFormat()
        records = list(await fmt.decode(raw_bytes))
        # decode returns one record per file; take the first
        return records[0]


class PixelAnalyser(Knot):
    """Receives the sanitised record; patient_id_hash is safe to log."""

    async def process(self, record: dict[str, Any], **_: Any) -> dict[str, Any]:
        shape = record["pixel_array_shape"]
        arr = np.frombuffer(record["pixel_data"], dtype=np.int16).reshape(shape)
        return {
            "patient_id_hash": record["patient_id_hash"],
            "modality": record["modality"],
            "mean_hu": float(arr.mean()),
            "shape": shape,
        }


dicom_bytes: bytes = open("study.dcm", "rb").read()

with Tapestry() as t:
    raw = Parameter("raw_bytes", bytes, default=dicom_bytes, _config=KnotConfig(id="raw"))
    loaded = DicomLoader(raw_bytes=raw, _config=KnotConfig(id="loader"))
    PixelAnalyser(record=loaded, _config=KnotConfig(id="analyser"))

result = await t.run(RunRequest())
analysis = result.outputs["analyser"]
print(analysis["patient_id_hash"])   # safe to log; never raw PatientID
```

---

## Anti-patterns

### Assuming redact=True covers all PHI

There is no `redact` parameter — redaction is always on. But the format layer only scrubs fields it knows about. Burned-in text in pixel data, PHI in free-text clinical notes, and NIfTI subject metadata from non-standard acquisition software are not covered. Treat the format layer as the minimum floor, not the complete PHI boundary.

### Passing raw DICOM bytes downstream before decoding

Passing `raw_bytes` directly to a downstream knot bypasses all PHI redaction. Always route through `DicomFormat.decode()` (or the equivalent format class) before any knot that logs, stores, or forwards data.

### Logging or caching the `pixel_data` bytes from intermediate knots

`pixel_data` fields in DICOM, EDF, and NIfTI records can be large (hundreds of MB per volume). Knot outputs are stored in lineage by default. Configure `validate_io=False` and avoid storing raw pixel bytes in history unless your storage backend is sized for it — see the medical triage example which skips history for this reason.

### Ignoring the OpenSlide C library requirement

`pip install pirn[health]` installs the `openslide-python` binding but NOT the C library. `OpenSlideFormat` will raise `ImportError` at decode time on systems where `openslide-tools` (or the equivalent) is not installed at the OS level.

### Using BrainVisionFormat without a zip bundle

`BrainVisionFormat` expects a zip archive containing `.vhdr`, `.vmrk`, and `.eeg` files. Passing a bare `.vhdr` file will fail. Build the zip before passing bytes to `decode()`.

### Expecting EdfPlusFormat annotations to always be present

`EdfPlusFormat` emits a signal record per channel plus one annotation record. The annotation record has the key `_edfplus_annotations`. If the source file contains no TAL annotations the list will be empty, not absent. Downstream knots must handle both cases.

### Treating SDTM XPT first-record metadata as a separate record type

`SdtmXptFormat` emits all rows as records with the same shape, but the first record carries an additional `_metadata` key (`column_labels`, `file_label`). Knots that iterate all records must guard against this extra key rather than assuming uniform shape.

---

## Constraints and gotchas

- **Whole-file buffering.** All health format connectors are `BatchFileFormat` subclasses: the full payload must fit in memory before decoding begins. For large DICOM series or NIfTI volumes, size accordingly.
- **NIfTI uses a temp file.** `NiftiFormat` writes bytes to a temporary file and calls `nibabel.load()` on the path. The temp file is deleted after decode. This is not a performance concern for normal use but will fail in environments with a read-only `/tmp`.
- **pyedflib version sensitivity.** EDF/BDF encode rejects the payload with `RuntimeError` if none of the four PHI-field setter methods (`set_patientname`, `set_patientcode`, `set_birthdate`, `set_admincode`) exist on the installed version. Pin `pyedflib>=0.1.42`.
- **pydicom 3.x rename.** `pydicom>=3` renamed `write_like_original` to `enforce_file_format`. `DicomFormat` handles both transparently; do not pass either kwarg manually.
- **defusedxml for XML formats.** `FhirXmlFormat` and `CdaXmlFormat` use `defusedxml` for safe parsing. Do not replace the parser with standard `xml.etree` in subclasses — doing so reintroduces XXE and billion-laughs attack surface.
- **pybids is optional.** `BidsDatasetFormat` degrades silently to plain zip extraction when `pybids` is not installed. BIDS-level validation (entity keys, suffix rules, dataset_description.json) is skipped. Install `pybids` explicitly if validation matters.
- **Sub-domain knots are importable stubs.** Heavy vendor SDKs (`pydicom`, `mne`, `nibabel`, `pyfaidx`, `pysam`, `fhir.resources`) are not imported at package load time. The `pirn.domains.health.*` knot classes are importable without the extra installed, but calling `process()` will fail at runtime if the underlying SDK is missing.

---

## Quick reference

| Format | Class | Extra | PHI redaction |
|---|---|---|---|
| DICOM | `DicomFormat` | `health` | `patient_id_hash`; PHI fields dropped |
| FHIR JSON | `FhirJsonFormat` | `health` | `identifier_hash`; name/DOB/address/telecom dropped |
| FHIR XML | `FhirXmlFormat` | `health` | Same as FhirJsonFormat |
| HL7 v2 | `Hl7v2Format` | `health` | PID 3,5,7,11,18,19,20 → `[REDACTED]` |
| CDA XML | `CdaXmlFormat` | `health` | name/birthTime/addr/telecom → `[REDACTED]` |
| EDF | `EdfFormat` | `health` | patientname/patientcode/birthdate/admincode stripped |
| EDF+ | `EdfPlusFormat` | `health` | Same as EdfFormat + annotation record |
| BDF | `BdfFormat` | `health` | Same as EdfFormat |
| BrainVision | `BrainVisionFormat` | `health` | SubjectName/SubjectID/InstitutionName stripped |
| NIfTI | `NiftiFormat` | `health` | None |
| BIDS | `BidsDatasetFormat` | `health` | None |
| OpenSlide (WSI) | `OpenSlideFormat` | `health` + system lib | Vendor patient keys stripped |
| mzML | `MzmlFormat` | `health` | None |
| Define-XML | `DefineXmlFormat` | `health` | None (no PHI) |
| SDTM XPT | `SdtmXptFormat` | `health` | None (pre-de-identified) |
| FASTA | `FastaFormat` | `genomics` | None |
| FASTQ | `FastqFormat` | `genomics` | None |
| VCF | `VcfFormat` | `genomics` | None |
| BCF | `BcfFormat` | `genomics` | None |

---

*See also: [pirn AGENTIC_USE.md](../../AGENTIC_USE.md)*
