# Phase 4 Progress Tracker

Single source of truth for what's shipped vs pending in the Phase 4
file-formats arc. Updated as commits land.

**Branch:** `feat/domain-knot-libraries`
**Latest commit:** `4b5635a` (Round 3 cleanup + archive)
**Suite:** 3507 passing, 19 skipped, 0 failing
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

## Wave B3 — healthcare imaging (5/5 — commits 57d0220, 51d7f43)

- [x] `dicom_format.py` — `DicomFormat` (pydicom; PHI-hash safety; 36 tests)
- [x] `nifti_format.py` — `NiftiFormat` (nibabel; tempfile)
- [x] `bids_dataset_format.py` — `BidsDatasetFormat` (zip bundle + pybids)
- [x] `open_slide_format.py` — `OpenSlideFormat` (read-only; PHI metadata stripped)
- [x] `mzml_format.py` — `MzmlFormat` (pyteomics + lxml)

## Wave B2 — healthcare clinical (6/6 — commit 51d7f43)

- [x] `fhir_json_format.py` — `FhirJsonFormat` (fhir.resources; PHI hashed/stripped)
- [x] `fhir_xml_format.py` — `FhirXmlFormat` (fhir.resources + lxml)
- [x] `hl7v2_format.py` — `Hl7v2Format` (python-hl7; PID PHI redacted)
- [x] `cda_xml_format.py` — `CdaXmlFormat` (lxml + defusedxml)
- [x] `define_xml_format.py` — `DefineXmlFormat` (CDISC; no PHI)
- [x] `sdtm_xpt_format.py` — `SdtmXptFormat` (pyreadstat)

## Wave B5 — healthcare biosignal (4/4 — commit 51d7f43)

- [x] `edf_format.py` — `EdfFormat` (pyedflib; PHI header redacted)
- [x] `edf_plus_format.py` — `EdfPlusFormat` (extends EdfFormat + TAL annotations)
- [x] `bdf_format.py` — `BdfFormat` (pyedflib; 24-bit BDF variant)
- [x] `brainvision_format.py` — `BrainVisionFormat` (mne + pure-Python fallback)

## Wave C1 — audio (6/6 — commit e37519f)

- [x] `wav_format.py` — `WavFormat` (stdlib; no optional deps)
- [x] `flac_format.py` — `FlacFormat` (soundfile)
- [x] `ogg_format.py` — `OggFormat` (soundfile)
- [x] `mp3_format.py` — `Mp3Format` (pydub; skips on Python 3.13+ — pyaudioop removed)
- [x] `aac_format.py` — `AacFormat` (pydub; same skip condition)
- [x] `m4a_format.py` — `M4aFormat` (pydub; same skip condition)

## Wave C2 — oil & gas (7/7 — commit e37519f)

- [x] `segy_format.py` — `SegyFormat` (segyio; tempfile)
- [x] `las_format.py` — `LasFormat` (lasio)
- [x] `dlis_format.py` — `DlisFormat` (dlisio; decode-only)
- [x] `witsml_format.py` — `WitsmlFormat` (defusedxml + lxml)
- [x] `prodml_format.py` — `ProdmlFormat` (defusedxml + lxml)
- [x] `resqml_format.py` — `ResqmlFormat` (defusedxml + lxml)
- [x] `segd_format.py` — `SegdFormat` (pure-Python GH1 fallback; decode-only)

## Wave E — specialty science (5/5 — commit e37519f)

- [x] `fits_format.py` — `FitsFormat` (astropy)
- [x] `asdf_format.py` — `AsdfFormat` (asdf)
- [x] `netcdf4_format.py` — `Netcdf4Format` (multi-group netCDF4; distinct from Wave A2 NetcdfFormat)
- [x] `root_format.py` — `RootFormat` (uproot; decode-only)
- [x] `grib_format.py` — `GribFormat` (cfgrib; decode-only)

## Archive support — tar/zip (1/1 — commit 4b5635a)

- [x] `archive_file_format.py` — `ArchiveFileFormat` — full read/write for tar, tar.gz, tar.bz2, tar.zst, zip

---

## Cleanup completed (commit 4b5635a)

- [x] **B4a**: moved module-level helpers in fasta/fastq/vcf/bcf into class `@staticmethod`s

---

## Remaining — Block 9 Documentation & Polish

- [ ] `docs/domains/data.md`
- [ ] `docs/domains/agents.md`
- [ ] `docs/domains/ml.md`
- [ ] `docs/domains/health.md`
- [ ] `docs/domains/signal.md`
- [ ] `docs/domains/oilgas.md`
- [ ] `docs/connectors/index.md` — connector matrix
- [ ] `docs/contributing/domain-knots.md` — style guide
- [ ] Update `README.md`
- [ ] `CHANGELOG.md` entry
- [ ] mkdocs nav updated

---

## How to resume

1. Verify state: `uv run pytest tests/unit/ --no-header -q` — should report 3507 passing, 19 skipped, 0 failing.
2. Proceed to Block 9 documentation.

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
| B2 healthcare clinical | ✅ | 6 | 56 |
| B3 healthcare imaging | ✅ | 5 | 36+31 |
| B5 healthcare biosignal | ✅ | 4 | 49 |
| C1 audio | ✅ | 6 | 24 (3 skip) |
| C2 oil & gas | ✅ | 7 | 32 (4 skip) |
| E specialty | ✅ | 5 | 9 (4 skip) |
| Archive (tar/zip) | ✅ | 1 | (covered by CompressedFileFormat tests) |
| **TOTAL** | | **~98 / ~98** | **~846** |
