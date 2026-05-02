# Phase 4 Progress Tracker

Single source of truth for what's shipped vs pending in the Phase 4
file-formats arc. Updated as commits land.

**Branch:** `feat/domain-knot-libraries`
**Latest commit:** `4b2bdbd` (Round 2)
**Suite:** 3261 passing, 6 skipped, 0 failing
**PR:** [#13](https://github.com/snoodleboot-io/pirn/pull/13) (draft)

## Foundation — shipped (commit ae90db3)

- [x] `pirn/domains/connectors/file_format.py` — refined base with `streaming` property + `_drain_bytes` / `_drain_records` helpers
- [x] `pirn/domains/connectors/file_formats/streaming_file_format.py` — `StreamingFileFormat` marker base
- [x] `pirn/domains/connectors/file_formats/batch_file_format.py` — `BatchFileFormat` with `_decode_full` / `_encode_full` dispatch
- [x] `pirn/domains/connectors/file_formats/compressed_file_format.py` — codec wrapper
- [x] `pirn/domains/connectors/file_formats/archive_file_format.py` — tar/zip placeholder (read/write impls in Wave A4)
- [x] `pirn/domains/connectors/file_formats/codec.py` — `Codec` interface
- [x] `pirn/domains/connectors/file_formats/codecs/__init__.py` — codec package
- [x] `pirn/domains/data/sources/file_source.py` — `FileSource` knot
- [x] `pirn/domains/data/sources/directory_source.py` — `DirectorySource`
- [x] `pirn/domains/data/sinks/file_sink.py` — `FileSink`
- [x] `pirn/domains/data/lakehouse/lakehouse_table.py` — interface (scan/append/overwrite/merge/history)
- [x] `pirn/domains/data/lakehouse/lakehouse_table_source.py` — knot
- [x] `pirn/domains/data/lakehouse/lakehouse_table_sink.py` — knot
- [x] `tests/unit/domains/connectors/file_formats/_format_round_trip.py` — `FormatRoundTrip` test helper

## Wave A1 — universal tabular (11/11 — commit 86436b2)

- [x] `parquet_format.py` — `ParquetFormat` (pyarrow)
- [x] `csv_format.py` — `CsvFormat`
- [x] `tsv_format.py` — `TsvFormat`
- [x] `json_format.py` — `JsonFormat`
- [x] `jsonl_format.py` — `JsonlFormat`
- [x] `arrow_ipc_format.py` — `ArrowIpcFormat`
- [x] `avro_format.py` — `AvroFormat` (fastavro)
- [x] `orc_format.py` — `OrcFormat` (pyarrow.orc)
- [x] `feather_format.py` — `FeatherFormat`
- [x] `xlsx_format.py` — `XlsxFormat` (openpyxl read_only=True / xlsxwriter)
- [x] `ods_format.py` — `OdsFormat` (odfpy)

## Wave A4 — compression codecs (5/5 — commit 86436b2)

- [x] `codecs/gzip_codec.py` — `GzipCodec` (stdlib)
- [x] `codecs/bzip2_codec.py` — `Bzip2Codec` (stdlib)
- [x] `codecs/zstd_codec.py` — `ZstdCodec` (zstandard, true streaming)
- [x] `codecs/snappy_codec.py` — `SnappyCodec` (python-snappy framed)
- [x] `codecs/lz4_codec.py` — `Lz4Codec` (lz4.frame)
- [x] `tests/.../test_compressed_file_format.py` — composability per codec

**Archive support (tar/zip)** intentionally deferred — `archive_file_format.py` raises NotImplementedError. Add to a follow-up wave.

## Wave A3 — lakehouse (3/3 — commit 86436b2)

- [x] `lakehouse/delta/delta_table.py` — `DeltaTable` (deltalake) — full surface
- [x] `lakehouse/iceberg/iceberg_table.py` — `IcebergTable` (pyiceberg) — `merge` raises NotImplementedError (pyiceberg 0.6 no native MERGE)
- [x] `lakehouse/hudi/hudi_table.py` — `HudiTable` — read-only, append/overwrite/merge raise NotImplementedError (Hudi Python writer ecosystem immature)

## Wave A2 — scientific tabular (6/6 — commit 4b2bdbd)

- [x] `hdf5_format.py` — `Hdf5Format` (h5py)
- [x] `zarr_format.py` — `ZarrFormat` (zarr v3 ZipStore via tempfile)
- [x] `numpy_npy_format.py` — `NumpyNpyFormat`
- [x] `numpy_npz_format.py` — `NumpyNpzFormat`
- [x] `matlab_mat_format.py` — `MatlabMatFormat` (scipy.io v5)
- [x] `netcdf_format.py` — `NetcdfFormat` (netCDF4 via tempfile)

## Wave B1 — documents (8/8 — commit 4b2bdbd)

- [x] `pdf_format.py` — `PdfFormat` (pypdf read, reportlab write)
- [x] `docx_format.py` — `DocxFormat` (python-docx)
- [x] `pptx_format.py` — `PptxFormat` (python-pptx)
- [x] `html_format.py` — `HtmlFormat` (beautifulsoup4 + lxml)
- [x] `plain_text_format.py` — `PlainTextFormat` (StreamingFileFormat)
- [x] `markdown_format.py` — `MarkdownFormat` (markdown-it-py)
- [x] `epub_format.py` — `EpubFormat` (ebooklib)
- [x] `rtf_format.py` — `RtfFormat` (striprtf read; manual write)

## Wave B4 — genomics (7/7 — commit 4b2bdbd)

Text formats:
- [x] `fasta_format.py` — `FastaFormat` (stdlib)
- [x] `fastq_format.py` — `FastqFormat` (stdlib)
- [x] `vcf_format.py` — `VcfFormat` (stdlib)
- [x] `bcf_format.py` — `BcfFormat` (pysam binary)

Alignment formats:
- [x] `sam_format.py` — `SamFormat` (pysam)
- [x] `bam_format.py` — `BamFormat` (pysam)
- [x] `cram_format.py` — `CramFormat` (pysam, requires reference_fasta for write)

⚠️ **B4a flagged a convention violation:** module-level free helpers in fasta/fastq/vcf/bcf — should be wrapped into class staticmethods. **Cleanup pending.**

## Wave C3 — geospatial (5/5 — commit 4b2bdbd)

- [x] `shapefile_format.py` — `ShapefileFormat` (pyshp; zipped bundle)
- [x] `geojson_format.py` — `GeoJsonFormat` (StreamingFileFormat; stdlib)
- [x] `kml_format.py` — `KmlFormat` (simplekml + lxml)
- [x] `geotiff_format.py` — `GeotiffFormat` (rasterio)
- [x] `geopackage_format.py` — `GeopackageFormat` (fiona) — 7 tests skip on Python 3.14 (no fiona wheels yet)

## Wave D1 — ML artifacts (7/7 — commit 4b2bdbd)

- [x] `onnx_format.py` — `OnnxFormat` (onnx)
- [x] `safetensors_format.py` — `SafetensorsFormat` (safetensors; RCE-safe by design)
- [x] `joblib_format.py` — `JoblibFormat` (joblib + **mandatory `_Signer`** unless `allow_unsigned=True`)
- [x] `pytorch_format.py` — `PytorchFormat` (torch; `weights_only=True` default; signer mandatory for `weights_only=False` unless `allow_unsigned=True`)
- [x] `tf_saved_model_format.py` — `TfSavedModelFormat` (zip-bundle pattern)
- [x] `gguf_format.py` — `GgufFormat` (gguf via tempfile)
- [x] `tflite_format.py` — `TfliteFormat` (tflite_runtime)

## Wave D2 — images (5/5 — commit 4b2bdbd)

- [x] `tiff_format.py` — `TiffFormat` (tifffile + Pillow; multi-page → record per page)
- [x] `png_format.py` — `PngFormat` (Pillow; lossless)
- [x] `jpeg_format.py` — `JpegFormat` (Pillow; lossy)
- [x] `webp_format.py` — `WebpFormat` (Pillow; lossless flag)
- [x] `heic_format.py` — `HeicFormat` (pillow-heif)

---

## NOT YET SHIPPED — Round 3 (33 formats, 1 partial)

All Round 3 agents hit API rate limits before completing work. The
prompts I dispatched are documented in this session's chat history
and can be re-issued verbatim once quota resets.

### Wave B2 — healthcare clinical (0/6)

- [ ] `fhir_json_format.py` — `FhirJsonFormat` (fhir.resources)
- [ ] `fhir_xml_format.py` — `FhirXmlFormat` (fhir.resources XML)
- [ ] `hl7v2_format.py` — `Hl7v2Format` (python-hl7)
- [ ] `cda_xml_format.py` — `CdaXmlFormat` (lxml + defusedxml)
- [ ] `define_xml_format.py` — `DefineXmlFormat` (CDISC Define-XML 2.x)
- [ ] `sdtm_xpt_format.py` — `SdtmXptFormat` (pyreadstat)

### Wave B3 — healthcare imaging (1 partial / 5)

- [⚠️] `dicom_format.py` — `DicomFormat` (pydicom). **Source written (287 lines, untracked) by B3 agent before rate limit. NO TEST FILE. Includes PHI-hash safety per spec.** Decision needed: commit-as-is + add test in next session, OR revert and rewrite cleanly.
- [ ] `nifti_format.py` — `NiftiFormat` (nibabel; tempfile)
- [ ] `bids_dataset_format.py` — `BidsDatasetFormat` (pybids; zip bundle)
- [ ] `open_slide_format.py` — `OpenSlideFormat` (openslide-python; read-only)
- [ ] `mzml_format.py` — `MzmlFormat` (pyteomics)

### Wave B5 — healthcare biosignal (0/4)

- [ ] `edf_format.py` — `EdfFormat` (pyedflib)
- [ ] `edf_plus_format.py` — `EdfPlusFormat(EdfFormat)` with annotations
- [ ] `bdf_format.py` — `BdfFormat` (pyedflib)
- [ ] `brainvision_format.py` — `BrainVisionFormat` (mne; zip bundle of .eeg/.vhdr/.vmrk)

### Wave C1 — audio (0/6)

- [ ] `wav_format.py` — `WavFormat` (stdlib wave + numpy)
- [ ] `flac_format.py` — `FlacFormat` (soundfile)
- [ ] `mp3_format.py` — `Mp3Format` (pydub + ffmpeg)
- [ ] `ogg_format.py` — `OggFormat` (soundfile)
- [ ] `aac_format.py` — `AacFormat` (pydub + ffmpeg)
- [ ] `m4a_format.py` — `M4aFormat` (pydub + ffmpeg)

### Wave C2 — oil & gas (0/7)

- [ ] `segy_format.py` — `SegyFormat` (segyio)
- [ ] `las_format.py` — `LasFormat` (lasio)
- [ ] `dlis_format.py` — `DlisFormat` (dlisio; write may NotImplementedError)
- [ ] `witsml_format.py` — `WitsmlFormat` (lxml + defusedxml)
- [ ] `prodml_format.py` — `ProdmlFormat` (lxml + defusedxml)
- [ ] `resqml_format.py` — `ResqmlFormat` (lxml + defusedxml; HDF5 sidecar deferred)
- [ ] `segd_format.py` — `SegdFormat` (segpy; encode may NotImplementedError)

### Wave E — specialty (0/5)

- [ ] `root_format.py` — `RootFormat` (uproot)
- [ ] `fits_format.py` — `FitsFormat` (astropy.io.fits)
- [ ] `grib_format.py` — `GribFormat` (cfgrib; encode NotImplementedError)
- [ ] `netcdf4_format.py` — `Netcdf4Format` (netCDF4 multi-group; distinct from Wave A2's NetcdfFormat)
- [ ] `asdf_format.py` — `AsdfFormat` (asdf)

### Tar/zip archive support (deferred from Wave A4)

- [ ] `archive_file_format.py` — implement `read` / `write` for `tar`, `tar.gz`, `tar.bz2`, `tar.zst`, `zip`. Currently raises NotImplementedError.

---

## Cleanup pending (separate from Round 3 work)

- [ ] **B4a module-level free helpers** — `fasta_format.py`, `fastq_format.py`, `vcf_format.py`, `bcf_format.py` have parse/serialise helpers at module scope. Wrap into class `@staticmethod`s per python.md "no free helpers" rule. Cf. SparkCompute split pattern.
- [ ] **Verify epub/hdf5 tests** — B4a agent flagged "pre-existing failures" in `test_epub_format.py` and `test_hdf5_format.py` while running. Current suite shows 0 failures, so they may have been transient agent-collision flakes — but worth a clean re-run on a quiet session to confirm.
- [ ] **B5-3 file-path validation** for genomics/oilgas knot stubs — flagged in `security-review-2026-05-01.md`. Defer until those stubs flip to real I/O.
- [ ] **Block 9 — Documentation & polish.** Per-domain docs (data/agents/ml/health/signal/oilgas), connector matrix, contributing guide, README, CHANGELOG, mkdocs nav. Held all session waiting for the surface to settle. After Round 3 + cleanup, this is the natural close.

---

## How to resume

1. Verify state: `cd pirn && uv run pytest tests/unit/ --no-header -q` should report 3261 passing, 6 skipped.
2. Decide DICOM disposition: commit `pirn/domains/connectors/file_formats/dicom_format.py` (untracked) + add test, OR revert it and rewrite as part of Wave B3.
3. Re-dispatch Round 3 — agent prompts are in this conversation's chat history. The PRD `phase4-data-formats-prd.md` has the wave plan; per-format spec is detailed enough to re-prompt cleanly.
4. After Round 3, do the cleanup items.
5. Block 9 last.

---

## Totals at a glance

| Wave | Status | Formats | Tests added |
|------|--------|---------|-------------|
| Foundation | ✅ | 7 scaffolding files | (interface tests via round_trip helper) |
| A1 universal tabular | ✅ | 11 | 132 |
| A4 compression | ✅ | 5 codecs + 1 wrapper | 38 |
| A3 lakehouse | ✅ | 3 | 56 |
| A2 scientific tabular | ✅ | 6 | 89 |
| B1 documents | ✅ | 8 | 113 |
| B4 genomics | ✅ | 7 | 88 |
| C3 geospatial | ✅ | 5 | 41 |
| D1 ML artifacts | ✅ | 7 | 78 |
| D2 images | ✅ | 5 | 47 |
| **B2 healthcare clinical** | ❌ | 0/6 | — |
| **B3 healthcare imaging** | ⚠️ partial | 1/5 (DICOM source untracked, no test) | — |
| **B5 healthcare biosignal** | ❌ | 0/4 | — |
| **C1 audio** | ❌ | 0/6 | — |
| **C2 oil & gas** | ❌ | 0/7 | — |
| **E specialty** | ❌ | 0/5 | — |
| Archive (tar/zip) | ❌ | 0/1 | — |
| **TOTAL** | | **64 / ~98** | **~682** |
