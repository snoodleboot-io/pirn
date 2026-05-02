# Changelog

All notable changes to pirn are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

#### Domain libraries (Phase 4)

Six domain-specific knot libraries are now available under `pirn/domains/`, each isolated behind its own optional extra:

- **`pirn[data]`** — tiered data-frame knots (Tier 1 dict batches, Tier 2 pandas/Polars/DuckDB/DataFusion, Tier 2.5 Modin, Tier 3 Ibis/Spark/Dask/Ray, Tier 4 Lance/Eland), plus tabular transform knots, validation integrations (Pandera, Great Expectations), and quality gates.
- **`pirn[agents]`** — LLM-backed knots, tool use, memory stores, planning, control gates, RAG, ReAct, multi-agent coordination, structured output extraction, and document processing pipelines.
- **`pirn[ml]`** — data prep, feature engineering, training, evaluation, deployment, shadow deployers, drift monitors, lineage tracking, and pre-built task pipelines (classification, regression, forecasting, NLP, computer vision).
- **`pirn[health]`** — DICOM, FHIR R4/R5, HL7v2, EDF/BDF, CDA, NIfTI/NIfTI2, FASTA, FASTQ, VCF, BCF connectors with PHI redaction and genomics processing knots.
- **`pirn[signal]`** — time-series transforms, DSP knots (FFT, filtering, windowing), audio format connectors (WAV, FLAC, MP3/Ogg, AIFF), and wavelet processing via PyWavelets.
- **`pirn[oilgas]`** — SEG-Y seismic, LAS well-log, and WITSML connectors; trace/header extraction and depth-log transform knots.

#### File format connectors — approximately 98 formats across 16 categories

**Wave 1 — Universal tabular formats (pirn/domains/connectors/file_formats/)**
- CSV, JSON, NDJSON, TSV, XML — streaming line-by-line row encoders/decoders
- Parquet, ORC, Avro, Feather — columnar binary formats via PyArrow/fastavro

**Wave 2 — Compression codecs (pirn/domains/connectors/file_formats/codecs/)**
- `GzipFormat`, `Bzip2Format` — stdlib; no extra required
- `ZstdFormat` (`pirn[zstd]`), `SnappyFormat` (`pirn[snappy]`), `Lz4Format` (`pirn[lz4]`)
- `CompressedFileFormat` — wraps any `StreamingFileFormat` with any codec

**Wave 2 — Archive formats**
- `TarFormat`, `ZipFormat` — streaming member extraction with zip-slip path-traversal protection

**Wave 2 — Lakehouse table formats**
- `DeltaFormat` (`pirn[delta]`) — Delta Lake read/write via `deltalake`
- `IcebergFormat` (`pirn[iceberg]`) — Apache Iceberg read via `pyiceberg`
- `HudiFormat` (`pirn[hudi]`) — Apache Hudi read via PyArrow (write path requires Spark/Java writer; Python write is not yet stable)

**Wave 3 — Office and document formats**
- `XlsxFormat` (`pirn[xlsx]`), `OdsFormat` (`pirn[ods]`) — spreadsheets
- `DocxFormat` (`pirn[docx]`), `PptxFormat` (`pirn[pptx]`) — Word/PowerPoint
- `PdfFormat` (`pirn[pdf]`) — read via pypdf, write via reportlab
- `RtfFormat` (`pirn[rtf]`), `EpubFormat` (`pirn[epub]`) — rich text / e-books
- `HtmlFormat` (`pirn[html]`), `MarkdownFormat` (`pirn[markdown]`) — markup

**Wave 3 — Scientific / multidimensional formats**
- `Hdf5Format` (`pirn[hdf5]`) — HDF5 dataset/group/attribute access via h5py
- `NetcdfFormat` (`pirn[netcdf]`) — NetCDF-4 via netCDF4
- `ZarrFormat` (`pirn[zarr]`) — chunked array stores
- `MatlabFormat` (`pirn[matlab]`) — MATLAB `.mat` files via SciPy

**Wave 3 — Image formats**
- `ImageFormat` (`pirn[image]`) — PNG, JPEG, WebP via Pillow
- `TiffFormat` (`pirn[tiff]`) — multi-page TIFF via tifffile + Pillow
- `HeicFormat` (`pirn[heic]`) — HEIC/HEIF via pillow-heif

**Wave 3 — Geospatial formats**
- `GeoJsonFormat` (`pirn[geojson]`), `ShapefileFormat` (`pirn[shapefile]`)
- `KmlFormat` (`pirn[kml]`), `GeoTiffFormat` (`pirn[geotiff]`), `GeoPackageFormat` (`pirn[geopackage]`)

**Wave 3 — ML artifact formats**
- `OnnxFormat` (`pirn[onnx]`) — whole-model protobuf with optional `onnx.checker` validation
- `SafetensorsFormat` (`pirn[safetensors]`) — RCE-safe Hugging Face tensor storage
- `JoblibFormat` (`pirn[joblib]`) — joblib/pickle with mandatory signer or explicit `allow_unsigned` acknowledgement
- `PytorchFormat` (`pirn[pytorch]`) — PyTorch state dicts; defaults `weights_only=True`; full-model loading requires signer
- `TfSavedModelFormat` (`pirn[tensorflow]`) — SavedModel directory bundled as ZIP
- `GgufFormat` (`pirn[gguf]`) — llama.cpp quantised LLM weights
- `TfliteFormat` (`pirn[tflite]`) — TFLite FlatBuffer models

**Wave 4 — Healthcare formats (pirn/domains/connectors/file_formats/healthcare/)**
- `DicomFormat` (`pirn[health]`) — DICOM image/RT/SR with built-in PHI redaction
- `FhirFormat` (`pirn[health]`) — FHIR R4/R5 JSON bundles via fhir.resources
- `Hl7v2Format` (`pirn[health]`) — HL7v2 ADT/ORM/ORU pipe-encoded messages with PHI tag stripping
- `EdfFormat` (`pirn[health]`) — EDF/BDF physiological signal files via pyedflib; PHI-bearing header fields scrubbed on request
- `CdaFormat` (`pirn[health]`) — CDA R2 XML clinical documents with configurable PHI tag redaction
- `NiftiFormat` (`pirn[health]`) — NIfTI-1 and NIfTI-2 neuroimaging via nibabel; BIDS companion sidecar support; zip-slip-safe BIDS archive extraction

**Wave 4 — Genomics formats**
- `FastaFormat` (`pirn[genomics]`) — FASTA sequence files via pyfaidx
- `FastqFormat` (`pirn[genomics]`) — FASTQ read files with quality score parsing
- `VcfFormat` (`pirn[genomics]`) — VCF variant call files via pysam
- `BcfFormat` (`pirn[genomics]`) — BCF binary variant files via pysam

#### Convenience aggregate extras

- `pirn[all-frames]` — all Tier-2 single-machine CPU frame engines (polars, pandas, pyarrow, duckdb, datafusion)
- `pirn[all-lazy]` — all Tier-3 push-down/lazy engines (ibis, pyspark, ray[data], dask)
- `pirn[all-domains]` — all domain library dependencies
- `pirn[all-db]`, `pirn[all-storage]`, `pirn[all-stream]`, `pirn[all-saas]`, `pirn[all-observability]` — groupings for connector categories

#### Documentation

- `docs/domains/agents.md` — agents domain reference: interfaces, sub-packages, code examples
- `docs/domains/ml.md` — ML domain reference: artifact formats with security properties, providers, sub-packages, code examples
- Domain libraries section added to README
- CHANGELOG introduced (this file)

### Security

- **PHI redaction** — DICOM, FHIR, HL7v2, EDF/BDF, and CDA format connectors include configurable PHI-field scrubbing. Redaction events are content-addressed through pirn's lineage layer so every scrub is auditable.
- **ML deserialization guards** — `JoblibFormat` and `PytorchFormat` constructors refuse unsigned construction. Production use requires a `_Signer` (HMAC-SHA256 signs before emission; verifies before load). Dev/test must explicitly pass `allow_unsigned=True`.
- **Zip-slip protection** — `ZipFormat`, `TarFormat`, `TfSavedModelFormat`, and `NiftiFormat` (BIDS archive extraction) guard against absolute and parent-directory member paths.
- **`weights_only=True` default** — `PytorchFormat` defaults to PyTorch's safe-mode loader, which restores tensor data only and refuses arbitrary callables.

### Fixed

- Removed module-level constants from domain connector files; moved to class-level or instance attributes per SOLID conventions.
- Removed nested function definitions from connector encode/decode paths.
- Replaced `Protocol` usage with explicit interface base classes (`LLMProvider`, `Tool`, `MemoryStore`, `EmbeddingProvider`, `FeatureStoreProvider`, `ImageEncoderProvider`, `LineageStore`) in line with pirn's one-class-per-file, interface-not-Protocol convention.
- Enforced one class per file throughout `pirn/domains/`.
- Corrected import ordering (stdlib → third-party → pirn-internal) in newly added modules.
- Suppressed `pyright` `reportMissingImports` for optional heavy extras (onnx, torch, tensorflow, etc.) that are imported lazily.

---

[Unreleased]: https://github.com/snoodleboot-io/pirn/compare/v0.3.0...HEAD
