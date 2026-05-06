# Health Domain

pirn's health domain covers the full stack of healthcare and life-science data: medical imaging (DICOM, NIfTI, whole-slide), clinical interoperability (FHIR, HL7 v2, CDA), biosignal recording (EDF, BDF, BrainVision), genomics (FASTA, FASTQ, VCF/BCF), clinical trials (SDTM, Define-XML, ADaM), and wearable sensor data. Every connector and format class in this domain treats PHI safety as a first-class requirement, not an afterthought.

---

## PHI Safety

pirn's health connectors follow a single consistent principle: **formats are the audited surface**. The decode path of every format that touches Protected Health Information (PHI) strips or hashes identifiers before handing records downstream. Downstream knots receive sanitised records only; they cannot accidentally log, cache, or forward raw PHI through the standard pipeline surface.

### Hashing vs. redaction

The pattern varies slightly by what the field carries:

| Field type | Treatment |
|---|---|
| Patient / subject identifier (one primary key per format) | SHA-256 hex digest emitted under a `*_hash` key |
| Name, birth date, address, phone / email | Dropped entirely from decoded records |
| Free-text fields that routinely contain PHI | Dropped entirely |
| HIPAA Safe Harbor quasi-identifiers | Dropped entirely |
| Structured PHI in fixed-width headers (EDF/BDF) | Replaced with `"[REDACTED]"` on encode |

Hashing identifiers (rather than dropping them) preserves cohort-level linkage while preventing direct re-identification. A pipeline that needs to cross-reference patients across runs can compare hashes without ever materialising the raw ID.

### The carve-out philosophy

Formats treat the PHI carve-out as **load-bearing**. If you need re-identifiable access — for a legal hold, a regulatory submission, or an authorised review — you must operate directly against the source bytes with your own access controls. The pirn connector layer is not that path.

### Redacted fields by format

| Format | Identifier hashed | Fields dropped / redacted |
|---|---|---|
| `DicomFormat` | `PatientID` → `patient_id_hash` (SHA-256) | `PatientName`, `PatientBirthDate`, `PatientAddress`, `PatientTelephoneNumbers`, `PatientComments`, `AdditionalPatientHistory`, `EthnicGroup`, `Occupation`, `PatientAge`, `PatientWeight`, `PatientSize`, `PatientBodyMassIndex`, and several more |
| `FhirJsonFormat` | `identifier` → `identifier_hash` (SHA-256) | `name`, `birthDate`, `address`, `telecom` |
| `FhirXmlFormat` | `identifier` → `identifier_hash` (SHA-256) | `name`, `birthDate`, `address`, `telecom` |
| `Hl7v2Format` | — | PID.3 (MRN), PID.5 (name), PID.7 (DOB), PID.11 (address), PID.18 (account number), PID.19 (SSN), PID.20 (driver's license) replaced with `"[REDACTED]"` |
| `CdaXmlFormat` | — | Patient `name`, `birthTime`, `addr`, `telecom` replaced with `"[REDACTED]"` |
| `EdfFormat` / `EdfPlusFormat` / `BdfFormat` | — | `patientname`, `patientcode`, `birthdate`, `admincode` stripped on decode; `"[REDACTED]"` written on encode |
| `BrainVisionFormat` | — | `SubjectName`, `SubjectID`, `InstitutionName` stripped from `.vhdr` header |
| `OpenSlideFormat` | — | Vendor-specific keys such as `aperio.Patient`, `aperio.PatientID`, `hamamatsu.Reference`, `leica.Identifier`, `mirax.SLIDE_BARCODE` stripped from metadata |
| `DefineXmlFormat` | — | No PHI present (structural metadata only) |
| `SdtmXptFormat` | — | No PHI expected (de-identified before FDA submission) |

---

## Healthcare Imaging Formats

### DicomFormat

DICOM (Digital Imaging and Communications in Medicine) is the de-facto container for radiology, CT, MRI, ultrasound, and other modality output. `DicomFormat` is backed by `pydicom`.

**Cardinality:** one record per file.

**Record shape:**

```python
{
    "sop_instance_uid":  str,           # SOPInstanceUID
    "patient_id_hash":   str,           # SHA-256 hex digest of PatientID
    "study_uid":         str,           # StudyInstanceUID
    "series_uid":        str,           # SeriesInstanceUID
    "modality":          str,           # e.g. "CT", "MR", "US"
    "pixel_array_shape": tuple[int, ...],  # voxel dimensions
    "pixel_data":        bytes,         # raw PixelData
    "metadata":          Mapping,       # sanitised tag/value pairs
}
```

**Constructor params:** none (default construct: `DicomFormat()`).

**Limitations:**

- Whole-file buffering — the full DICOM payload must fit in memory before decoding.
- Pixel data is returned as raw bytes. To work with numpy arrays, pass `pixel_data` through a `numpy.frombuffer` step in a downstream knot.
- Encode writes a generic `SecondaryCaptureImageStorage` SOP class. Re-encoding real clinical images into a specific modality SOP class requires setting additional DICOM tags in the `metadata` dict and post-processing the output with `pydicom` directly.
- `pydicom>=3` renamed the `write_like_original` kwarg to `enforce_file_format`; `DicomFormat` handles both transparently.

---

### NiftiFormat

NIfTI (Neuroimaging Informatics Technology Initiative) is the standard container for MRI, fMRI, and structural neuroimaging. Backed by `nibabel`. Uses a temporary file internally because `nibabel.load` expects a filesystem path.

**Cardinality:** one record per file.

**Record shape:**

```python
{
    "shape":   tuple[int, ...],    # voxel dimensions, e.g. (256, 256, 180)
    "dtype":   str,                # numpy dtype name, e.g. "float32"
    "affine":  list[list[float]],  # 4x4 affine matrix (voxels → mm)
    "header":  dict,               # NIfTI header fields
    "data":    bytes,              # raw image array bytes (C-order)
}
```

**Constructor params:** none.

**Limitations:** No PHI redaction — NIfTI headers rarely carry patient metadata, but subject information embedded by some acquisition systems is not currently stripped. Validate source files through a DICOM-to-NIfTI conversion tool (e.g. `dcm2niix`) that strips identifiers before ingestion.

---

### BidsDatasetFormat

BIDS (Brain Imaging Data Structure) is a directory-layout convention for neuroimaging datasets. Because the layout is a directory tree, `BidsDatasetFormat` treats the "file" as a **zip bundle** of the entire dataset.

**Cardinality:** one record per file inside the zip bundle.

**Record shape:**

```python
{
    "relative_path": str,    # path within the BIDS dataset zip
    "content":       bytes,  # raw file bytes
}
```

**Constructor params:** none.

**Behaviour:** On read, `pybids` is used for layout validation when installed. If `pybids` is not installed the format silently degrades to plain zip extraction and emits the same record shape without BIDS-level validation. Write always produces a valid zip bundle regardless of `pybids` availability.

**Limitations:** Path traversal is rejected at both read and write time. HDF5 sidecar files embedded in the bundle are passed through as raw bytes only.

---

### OpenSlideFormat

OpenSlide supports whole-slide imaging (WSI) formats including Aperio SVS, Hamamatsu NDPI, Leica SCN, and TIFF pyramids. **Read only** — encoding raises `NotImplementedError`.

**Cardinality:** one record per pyramid level.

**Record shape:**

```python
{
    "level":       int,
    "dimensions":  tuple[int, int],   # (width, height) at this level
    "downsample":  float,             # relative to level 0
    "tile_size":   int,               # configured tile size (pixels)
    "data":        bytes | None,      # RGB bytes if level fits threshold; else None
}
```

**Constructor params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `tile_size` | `int` | `256` | Tile size recorded in each level record |
| `max_decode_pixels` | `int \| None` | `None` | Levels whose total pixel count (width × height) ≤ this value have RGB bytes materialised into `data`; larger levels emit `data=None` |

**Limitations:** Requires the OpenSlide C library to be installed on the system in addition to the `openslide-python` binding. The `pirn[health]` extra installs the Python binding only; the C library must be installed separately (e.g. `apt install openslide-tools` on Debian/Ubuntu).

---

### MzmlFormat

mzML is an XML-based open standard for mass spectrometry data used in proteomics and metabolomics. Backed by `pyteomics` (read) and `lxml` (write).

**Cardinality:** one record per spectrum.

**Record shape:**

```python
{
    "scan_number":      int,
    "ms_level":         int,
    "retention_time":   float,   # seconds
    "mz_array":         bytes,   # raw float64 little-endian bytes
    "intensity_array":  bytes,   # raw float64 little-endian bytes
}
```

**Constructor params:** none.

---

## Healthcare Clinical Formats

### FhirJsonFormat

FHIR JSON bundles are the dominant format for exchanging clinical resources between health systems. Decodes a FHIR Bundle JSON payload and emits one record per resource entry; reconstructs a Bundle on encode.

**Cardinality:** one record per resource entry in the bundle (or one record if the payload is a bare resource rather than a Bundle).

**Record shape:**

```python
{
    "resource_type":  str,
    "resource_id":    str | None,
    "status":         str | None,
    "data":           dict,   # all non-PHI fields; identifier_hash added if identifier present
}
```

PHI redaction: `name`, `birthDate`, `address`, `telecom` dropped; `identifier` replaced by `identifier_hash` (SHA-256 of the JSON-serialised identifier object).

---

### FhirXmlFormat

Same semantics as `FhirJsonFormat` but operates on FHIR XML bundles. Uses `defusedxml` for safe parsing and `lxml` for serialisation. Record shape is identical to `FhirJsonFormat`.

---

### Hl7v2Format

HL7 v2 messages are pipe-delimited text. A file may contain multiple messages separated by consecutive MSH segments; each message is emitted as one record.

**Cardinality:** one record per HL7 message.

**Record shape:**

```python
{
    "message_type":       str,   # MSH.9
    "message_control_id": str,   # MSH.10
    "sending_facility":   str,   # MSH.4
    "receiving_facility": str,   # MSH.6
    "segments": [
        {
            "segment_id": str,
            "fields":     list[str],   # PHI fields replaced with "[REDACTED]"
        },
        ...
    ],
}
```

PHI redaction: PID fields 3, 5, 7, 11, 18, 19, 20 are replaced with `"[REDACTED]"`.

---

### CdaXmlFormat

CDA (Clinical Document Architecture) is an HL7 XML document standard used for clinical notes, discharge summaries, and structured documents. Uses `defusedxml` for safe parsing and `lxml` for serialisation.

**Cardinality:** one record per document.

**Record shape:**

```python
{
    "document_id":    str,
    "template_id":    str,
    "title":          str,
    "effective_time": str,
    "body":           dict[str, str],   # section code → text content
}
```

PHI redaction: patient `name`, `birthTime`, `addr`, `telecom` replaced with `"[REDACTED]"`.

---

### DefineXmlFormat

CDISC Define-XML 2.x is used for clinical trial dataset metadata submitted to regulatory agencies. It contains **no PHI** — only structural metadata describing dataset variables, types, labels, and codelists.

**Cardinality:** one record per `ItemDef` element.

**Record shape:**

```python
{
    "oid":       str,
    "name":      str,
    "data_type": str,
    "length":    int | None,
    "label":     str | None,
}
```

---

### SdtmXptFormat

SDTM XPT is the SAS Transport format mandated by FDA for clinical trial data submissions. Standard SDTM submissions are de-identified before FDA submission; no PHI sanitisation is applied. Backed by `pyreadstat`.

**Cardinality:** one record per row. The first record carries an additional `_metadata` key.

**Record shape (first record):**

```python
{
    "<col_name>": <value>,   # one key per dataset column
    ...,
    "_metadata": {
        "column_labels": {col_name: label, ...},
        "file_label":    str,
    }
}
```

Subsequent records omit `_metadata`.

---

## Healthcare Biosignal Formats

### EdfFormat

EDF (European Data Format) is a standard biosignal format for EEG, ECG, EMG, and other physiological recordings. Backed by `pyedflib`.

**Cardinality:** one record per signal channel.

**Record shape:**

```python
{
    "signal_index":  int,
    "label":         str,
    "sample_rate":   int,
    "n_samples":     int,
    "physical_min":  float,
    "physical_max":  float,
    "data":          bytes,   # raw float64 array bytes
}
```

PHI redaction: `patientname`, `patientcode`, `birthdate`, `admincode` are stripped from decoded records. On encode, these header fields are set to `"[REDACTED]"` via `pyedflib`'s writer API. If the `pyedflib` version does not expose the setter methods a `RuntimeWarning` is issued; if none of the four setters are available `RuntimeError` is raised (encode is rejected rather than silently writing PHI).

---

### EdfPlusFormat

EDF+ extends EDF with Time-stamped Annotation Lists (TAL). `EdfPlusFormat` subclasses `EdfFormat` and adds an annotation record to the decoded stream.

**Cardinality:** one record per signal channel, plus one annotation record.

The annotation record has shape:

```python
{
    "_edfplus_annotations": [
        {"onset": float, "duration": float, "text": str},
        ...
    ]
}
```

On encode, if the annotation record is present in the input stream, annotations are written back into the EDF+ file. PHI redaction is identical to `EdfFormat`.

---

### BdfFormat

BDF (BioSemi Data Format) is a 24-bit variant of EDF primarily used for high-density EEG recordings from BioSemi ActiveTwo amplifiers. Backed by `pyedflib` with `file_type=FILETYPE_BDF`. Record shape is identical to `EdfFormat`. PHI redaction is identical to `EdfFormat`.

---

### BrainVisionFormat

BrainVision is a three-file EEG format: `.vhdr` (INI-style header), `.vmrk` (markers/events), `.eeg` (raw binary). The pirn "payload" is a **zip archive** containing all three files.

**Cardinality:** one record per channel.

**Record shape:**

```python
{
    "channel_index": int,
    "channel_name":  str,
    "sample_rate":   float,
    "n_samples":     int,
    "data":          bytes,   # raw float64 array bytes
}
```

**Decoding:** Uses `mne` when available for full read support. Falls back to a minimal pure-Python parser if `mne` is not installed; the fallback supports `BINARY`/`MULTIPLEXED` data orientation only.

PHI redaction: `.vhdr` keys `SubjectName`, `SubjectID`, and `InstitutionName` are stripped from decoded records and replaced with `"[REDACTED]"` on encode.

---

## Sub-domains

### `pirn.domains.health.clinical`

Clinical data knots for EHR and CDS workflows.

| Knot | Description |
|---|---|
| `FhirPatientIngestor` | Decodes FHIR Bundles and emits sanitised patient records |
| `Hl7v2MessageParser` | Parses HL7 v2 messages from bytes |
| `PhiRedactor` | Explicit pass-through redaction knot for clinical record streams |
| `PatientCohortBuilder` | Filters a record stream into a named cohort by inclusion criteria |
| `DiagnosisCodeRollup` | Rolls ICD-10 leaf codes up to a configurable ancestor level |
| `Icd10CodeValidator` | Validates ICD-10-CM codes against a reference dictionary |
| `LoincMapper` | Maps local lab codes to LOINC identifiers |
| `LabResultNormalizer` | Normalises lab result units and reference ranges |
| `VitalSignsAggregator` | Aggregates vital sign observations into summary statistics |
| `EncounterTimelineAssembler` | Assembles an ordered encounter timeline per patient |
| `MedicationReconciliationPipeline` | Reconciles medication lists across encounters |
| `RxNormNormalizer` | Normalises drug names to RxNorm CUIs |
| `SnomedCtNormalizer` | Maps clinical terms to SNOMED CT concept IDs |
| `OmopCdmMapper` | Maps source records to OMOP CDM domain tables |
| `ReadmissionRiskScorer` | Produces a 30-day readmission risk score |
| `ClinicalNlpExtractor` | Extracts structured entities from clinical free text |
| `ClinicalTrialEligibilityFilter` | Filters patients against trial inclusion/exclusion criteria |
| `ClinicalDataQualityCheck` | Quality assessment knot; emits `Err` for records that fail quality checks (`ClinicalDataQualityGate` is a backward-compatible alias) |

---

### `pirn.domains.health.mri`

MRI acquisition and analysis knots.

| Knot | Description |
|---|---|
| `DicomIngestor` | Reads DICOM series from a directory and emits volume records |
| `NiftiConverter` | Converts DICOM volumes to NIfTI format |
| `BiasFieldCorrector` | N4 bias field correction via ANTs/SimpleITK |
| `BrainMaskExtractor` | Skull-stripping and brain mask extraction |
| `MotionCorrector` | Volume-to-volume motion correction |
| `ImageRegistrar` | Inter-subject or atlas registration |
| `IntensityNormalizer` | Normalises voxel intensity distributions |
| `AtlasAligner` | Aligns volumes to a standard atlas (MNI152, etc.) |
| `LesionSegmenter` | Lesion segmentation (white matter, tumour) |
| `VolumetricAnalyzer` | Computes regional volumetric statistics |
| `RegionOfInterestExtractor` | Extracts ROI time series from functional data |
| `RadiomicsExtractor` | Extracts radiomic features from structural images |
| `CorticalThicknessEstimator` | Estimates cortical thickness via surface-based analysis |
| `WhiteMatterAnalyzer` | White matter tract analysis (DTI/DWI) |

---

### `pirn.domains.health.eeg_meg`

EEG and MEG processing knots backed by `mne`.

| Knot | Description |
|---|---|
| `EegRawIngestor` | Loads EDF/EDF+/BDF/BrainVision files into MNE Raw objects |
| `MegRawIngestor` | Loads MEG data (FIF, CTF) into MNE Raw objects |
| `BandpassFilter` | Applies a bandpass filter to raw data |
| `NotchFilter` | Notch filter for power-line noise removal |
| `ArtifactRemover` | ICA-based artifact rejection |
| `EpochExtractor` | Segments continuous data into epochs around events |
| `EvokedResponseAverager` | Averages epochs to produce evoked responses |
| `PowerSpectrumEstimator` | Power spectral density estimation (Welch) |
| `TimeFrequencyDecomposer` | Time-frequency analysis (Morlet wavelet) |
| `CoherenceAnalyzer` | Spectral coherence between channels |
| `ConnectivityAnalyzer` | Functional/effective connectivity estimation |
| `SourceLocalizer` | Source-space reconstruction (minimum-norm, beamformer) |
| `SeizureDetector` | Rule-based and ML-based seizure onset detection |

---

### `pirn.domains.health.genomics`

NGS pipeline knots.

| Knot | Description |
|---|---|
| `FastqQualityController` | FASTQ quality filtering and trimming |
| `BwaAligner` | BWA-MEM alignment to a reference genome |
| `Bowtie2Aligner` | Bowtie2 alignment to a reference genome |
| `StarAligner` | STAR RNA-seq aligner |
| `GatkCaller` | GATK HaplotypeCaller variant calling |
| `BcftoolsCaller` | BCFtools variant calling |
| `VcfFilter` | VCF filtering by quality, depth, and annotation |
| `VcfMerger` | Merges multiple VCF files |
| `GvcfCombiner` | Combines per-sample GVCFs for joint genotyping |
| `SnpEffAnnotator` | Annotates variants with SnpEff |
| `VepAnnotator` | Annotates variants with Ensembl VEP |
| `CnvDetector` | Copy number variant detection |
| `StructuralVariantDetector` | SV detection from aligned reads |
| `ExpressionQuantifier` | RNA-seq expression quantification |
| `DifferentialExpressionAnalyzer` | Differential expression analysis |
| `PathwayEnricher` | Gene set / pathway enrichment analysis |
| `MultiOmicsIntegrator` | Integrates multi-omics datasets |
| `SingleCellClusterer` | Single-cell RNA-seq clustering |
| `GenomicsQCCheck` | Quality assessment knot for NGS metrics (`GenomicsQCGate` is a backward-compatible alias) |

---

### `pirn.domains.health.pathology`

Digital pathology knots for whole-slide image analysis.

| Knot | Description |
|---|---|
| `WsiTileExtractor` | Tiles whole-slide images into fixed-size patches |
| `TissueSegmenter` | Identifies tissue regions and discards background tiles |
| `CellDetector` | Nuclear/cell detection from H&E tiles |
| `MitosisCounter` | Counts mitotic figures in a tile set |
| `PathologyFeatureExtractor` | Extracts morphological features from cell populations |

---

### `pirn.domains.health.trials`

Clinical trial data management knots (CDISC/SDTM/ADaM).

| Knot | Description |
|---|---|
| `SdtmDomainValidator` | Validates SDTM datasets against domain rules |
| `AdamDatasetBuilder` | Builds ADaM datasets from SDTM source data |
| `DefineXmlGenerator` | Generates Define-XML 2.x metadata from dataset definitions |
| `MeddraNormalizer` | Maps adverse event terms to MedDRA hierarchy |
| `ClinicalEventAggregator` | Aggregates clinical events into analysis-ready records |
| `TreatmentEmergentClassifier` | Classifies treatment-emergent adverse events |
| `EstimandAlignedAnalyzer` | Applies estimand-aligned intercurrent event strategies |

---

### `pirn.domains.health.wearables`

Wearable and remote monitoring knots.

| Knot | Description |
|---|---|
| `EcgRPeakDetector` | R-peak detection from single-lead ECG signals |
| `HeartRateVariabilityAnalyzer` | HRV time-domain and frequency-domain metrics |
| `SleepStager` | Sleep stage classification from accelerometer + PPG |
| `StepCounter` | Step count from tri-axial accelerometer |
| `GlucoseMonitorProcessor` | Continuous glucose monitor data processing |
| `SpirometryAnalyzer` | Spirometry flow-volume curve analysis |

---

### `pirn.domains.health.protocols`

Connection interfaces for healthcare system backends.

| Class | Description |
|---|---|
| `FhirClient` | FHIR REST API client (read/write resources) |
| `PacsClient` | DICOM PACS client (C-FIND / C-MOVE) |
| `OmopConnection` | OMOP CDM database connection |
| `LabInstrumentConnection` | LIS/HL7 lab instrument interface |

---

## Install Extras and Dependencies

```bash
# Core health domain (MRI/imaging, EEG, genomics, FHIR)
pip install "pirn[health]"

# Genomics only (FASTA, FASTQ, VCF, BCF — subset of health)
pip install "pirn[genomics]"
```

| Extra | Libraries installed | What it enables |
|---|---|---|
| `health` | `pydicom>=2.4`, `mne>=1.6`, `nibabel>=5.2`, `pyfaidx>=0.7`, `pysam>=0.22`, `fhir.resources>=7.1`, `pyedflib>=0.1.42` | DICOM, NIfTI, BIDS, EDF/EDF+/BDF, BrainVision (via mne), FHIR JSON/XML, HL7 v2, CDA, Define-XML, SDTM XPT, OpenSlide, mzML; all clinical and genomics sub-domain knots |
| `genomics` | `pyfaidx>=0.7`, `pysam>=0.22` | FASTA, FASTQ, VCF, BCF file format connectors only |

Additional system-level dependencies not installed by pip:

- **OpenSlide C library** — required by `OpenSlideFormat`. Install via the OS package manager (`apt install openslide-tools`, `brew install openslide`).
- **ffmpeg** — not used by health formats (audio only), but required by `pirn[audio]` for MP3/AAC/M4A.

**See also:** [File Formats — Connectors](../api/file-formats.md), [Signal Domain](signal.md), [Data Domain](data.md)
