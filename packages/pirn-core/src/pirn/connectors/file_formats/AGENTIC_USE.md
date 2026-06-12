`pirn.connectors.file_formats` provides stateless `FileFormat` encode/decode implementations for 90+ file formats — it does not read from or write to storage; use `ObjectStoreReadSource`/`ObjectStoreWriteSink` or file knots for that.

---

## Mental model

A `FileFormat` is a pure codec: `encode(value) -> bytes` and `decode(bytes) -> value`. No connections, no state. Pass a format instance as a config constant to any knot that accepts a `file_format=` argument. Formats are grouped into categories: tabular, scientific, ML model, geospatial, health/genomics, document, audio/image, and oil & gas.

---

## Source map

```
pirn/domains/connectors/file_formats/
│
│  ── Tabular / columnar ──
├── parquet_format.py        ParquetFormat        — Apache Parquet (columnar, compressed)
├── csv_format.py            CsvFormat            — comma-separated values
├── tsv_format.py            TsvFormat            — tab-separated values
├── json_format.py           JsonFormat           — JSON (single object or array)
├── jsonl_format.py          JsonlFormat          — newline-delimited JSON
├── arrow_ipc_format.py      ArrowIpcFormat       — Apache Arrow IPC (zero-copy)
├── feather_format.py        FeatherFormat        — Feather v2 (Arrow-backed)
├── orc_format.py            OrcFormat            — Apache ORC
├── avro_format.py           AvroFormat           — Apache Avro (schema-embedded)
├── xlsx_format.py           XlsxFormat           — Excel workbook (.xlsx)
├── ods_format.py            OdsFormat            — OpenDocument Spreadsheet
│
│  ── Scientific / array ──
├── hdf5_format.py           Hdf5Format           — HDF5 (hierarchical datasets)
├── netcdf4_format.py        NetCdf4Format        — NetCDF-4 (earth/climate data)
├── netcdf_format.py         NetCdfFormat         — NetCDF classic (v3)
├── zarr_format.py           ZarrFormat           — Zarr chunked arrays
├── numpy_npy_format.py      NumpyNpyFormat       — single NumPy array (.npy)
├── numpy_npz_format.py      NumpyNpzFormat       — multiple NumPy arrays (.npz)
├── matlab_mat_format.py     MatlabMatFormat      — MATLAB .mat (v5/v7.3)
├── fits_format.py           FitsFormat           — FITS (astronomy)
├── grib_format.py           GribFormat           — GRIB (meteorology)
├── asdf_format.py           AsdfFormat           — ASDF (astrophysics)
├── root_format.py           RootFormat           — ROOT (particle physics)
│
│  ── ML models ──
├── onnx_format.py           OnnxFormat           — ONNX model graph
├── safetensors_format.py    SafetensorsFormat    — SafeTensors (fast, safe weights)
├── pytorch_format.py        PytorchFormat        — PyTorch state dict (.pt/.pth)
├── tflite_format.py         TfliteFormat         — TensorFlow Lite flatbuffer
├── tf_saved_model_format.py TfSavedModelFormat   — TensorFlow SavedModel directory
├── gguf_format.py           GgufFormat           — GGUF (llama.cpp quantised models)
├── joblib_format.py         JoblibFormat         — scikit-learn / joblib pickle
│
│  ── Geospatial ──
├── geojson_format.py        GeoJsonFormat        — GeoJSON features
├── geotiff_format.py        GeoTiffFormat        — GeoTIFF raster (georeferenced)
├── geopackage_format.py     GeopackageFormat     — GeoPackage (vector/raster SQLite)
├── shapefile_format.py      ShapefileFormat      — ESRI Shapefile (.shp/.dbf/.shx)
├── kml_format.py            KmlFormat            — KML (Google Earth)
├── las_format.py            LasFormat            — LAS point cloud
│
│  ── Health / clinical ──
├── dicom_format.py          DicomFormat          — DICOM medical imaging
├── nifti_format.py          NiftiFormat          — NIfTI neuroimaging
├── bids_dataset_format.py   BidsDatasetFormat    — BIDS dataset layout
├── edf_format.py            EdfFormat            — EDF biosignals (EEG, ECG)
├── edf_plus_format.py       EdfPlusFormat        — EDF+ (annotations)
├── bdf_format.py            BdfFormat            — BDF (BioSemi 24-bit EEG)
├── brainvision_format.py    BrainVisionFormat    — BrainVision (EEG header + data)
├── hl7v2_format.py          Hl7v2Format          — HL7 v2 messages
├── fhir_json_format.py      FhirJsonFormat       — FHIR R4 JSON resources
├── fhir_xml_format.py       FhirXmlFormat        — FHIR R4 XML resources
├── cda_xml_format.py        CdaXmlFormat         — HL7 CDA clinical documents
├── sdtm_xpt_format.py       SdtmXptFormat        — CDISC SDTM XPT (clinical trials)
├── define_xml_format.py     DefineXmlFormat      — CDISC Define-XML metadata
├── open_slide_format.py     OpenSlideFormat      — whole-slide imaging (SVS, NDPI)
├── mzml_format.py           MzmlFormat           — mzML mass spectrometry
│
│  ── Genomics ──
├── fasta_format.py          FastaFormat          — FASTA sequences
├── fastq_format.py          FastqFormat          — FASTQ sequences + quality
├── bam_format.py            BamFormat            — BAM aligned reads
├── sam_format.py            SamFormat            — SAM aligned reads (text)
├── cram_format.py           CramFormat           — CRAM compressed alignments
├── bcf_format.py            BcfFormat            — BCF binary variant calls
├── vcf_format.py            VcfFormat            — VCF variant calls (text)
│
│  ── Oil & gas / seismic ──
├── segy_format.py           SegyFormat           — SEG-Y seismic data
├── segd_format.py           SegdFormat           — SEG-D field recordings
├── dlis_format.py           DlisFormat           — DLIS well log data
├── las_format.py            LasFormat            — LAS well log (ASCII)
├── witsml_format.py         WitsmlFormat         — WITSML drilling/operations
├── prodml_format.py         ProdmlFormat         — PRODML production data
├── resqml_format.py         ResqmlFormat         — RESQML reservoir models
│
│  ── Document / text ──
├── pdf_format.py            PdfFormat            — PDF (extract text/bytes)
├── docx_format.py           DocxFormat           — Word document (.docx)
├── pptx_format.py           PptxFormat           — PowerPoint (.pptx)
├── epub_format.py           EpubFormat           — EPUB ebook
├── html_format.py           HtmlFormat           — HTML (parse or emit)
├── markdown_format.py       MarkdownFormat       — Markdown (parse or emit)
├── rtf_format.py            RtfFormat            — Rich Text Format
├── plain_text_format.py     PlainTextFormat      — UTF-8 text
│
│  ── Audio ──
├── wav_format.py            WavFormat            — WAV PCM audio
├── mp3_format.py            Mp3Format            — MP3 audio
├── flac_format.py           FlacFormat           — FLAC lossless audio
├── aac_format.py            AacFormat            — AAC audio
├── ogg_format.py            OggFormat            — Ogg Vorbis audio
├── m4a_format.py            M4aFormat            — M4A (AAC in MPEG-4)
│
│  ── Image ──
├── png_format.py            PngFormat            — PNG image
├── jpeg_format.py           JpegFormat           — JPEG image
├── tiff_format.py           TiffFormat           — TIFF image
├── webp_format.py           WebpFormat           — WebP image
├── heic_format.py           HeicFormat           — HEIC/HEIF image
│
│  ── Compressed / archive ──
├── compressed_file_format.py CompressedFileFormat — gzip/bzip2/zstd/lz4 wrapper
├── archive_file_format.py   ArchiveFileFormat    — tar/zip archive
├── batch_file_format.py     BatchFileFormat      — multi-record batch wrapper
├── streaming_file_format.py StreamingFileFormat  — streaming encode/decode wrapper
│
│  ── Codecs and primitives ──
├── codec.py                 Codec                — base: encode()/decode() pair
├── codecs/                  (compression codec impls — internal)
└── _html_stripper.py        (internal HTML text extractor)
```

---

## Canonical pattern

```python
from pirn.connectors.file_formats.parquet_format import ParquetFormat
from pirn.connectors.object_storage.s3_store import S3Store
from pirn.connectors.knots.object_store_read_source import ObjectStoreReadSource
from pirn.connectors.knots.object_store_write_sink import ObjectStoreWriteSink
from pirn import Tapestry, KnotConfig, RunRequest

fmt   = ParquetFormat()
store = S3Store(bucket="my-data", prefix="processed/")

with Tapestry() as t:
    raw       = ObjectStoreReadSource(store=store, key="input.parquet",
                                      file_format=fmt, _config=KnotConfig(id="read"))
    processed = TransformKnot(data=raw, _config=KnotConfig(id="transform"))
    ObjectStoreWriteSink(store=store, key="output.parquet",
                         file_format=fmt, data=processed, _config=KnotConfig(id="write"))

result = await t.run(RunRequest())
```

### Domain-specific format — DICOM

```python
from pirn.connectors.file_formats.dicom_format import DicomFormat

fmt = DicomFormat()
# decode(bytes) -> pydicom Dataset; encode(Dataset) -> bytes
```

### Compressed wrapper

```python
from pirn.connectors.file_formats.compressed_file_format import CompressedFileFormat
from pirn.connectors.file_formats.json_format import JsonFormat

fmt = CompressedFileFormat(inner=JsonFormat(), codec="zstd")
# encode(value) -> zstd-compressed JSON bytes
```

---

## Anti-patterns

**Holding format state between calls** — `FileFormat` implementations are stateless singletons. Create once, share across knots and tapestries.

**Wrapping a streaming format in `BatchFileFormat` without sizing** — `BatchFileFormat` buffers records into batches. Not specifying `batch_size` can cause unbounded memory use with large record streams.

**Using `PdfFormat` to reconstruct structured data** — `PdfFormat.decode()` extracts raw text. It does not reconstruct tables, form fields, or layout. Use a dedicated extraction pipeline if structured content is needed.

---

## Constraints and gotchas

- **Domain-specific formats require their own extras.** `pirn[dicom]`, `pirn[genomics]`, `pirn[segy]`, `pirn[ml-formats]`, etc. Check `pyproject.toml` for exact names.
- **`SegyFormat` and `DlisFormat` are read-only.** `encode()` raises `NotImplementedError` — these are read formats only.
- **`BamFormat` and `CramFormat` require a reference genome for CRAM decoding.** Pass `reference_path=` to the constructor.
- **`TfSavedModelFormat` encodes/decodes a directory, not a single file.** The store knot must support directory-level reads and writes.
- **`CompressedFileFormat` wraps any inner format.** Supported codecs: `"gzip"`, `"bzip2"`, `"zstd"`, `"lz4"`.
- **`StreamingFileFormat` yields records lazily.** Use with streaming knots; do not collect into memory with large files.

---

## Quick reference

| Format | Class | Extra |
|--------|-------|-------|
| Parquet | `ParquetFormat` | base |
| CSV / TSV | `CsvFormat`, `TsvFormat` | base |
| JSON / JSONL | `JsonFormat`, `JsonlFormat` | base |
| Arrow IPC | `ArrowIpcFormat` | base |
| ORC | `OrcFormat` | `pirn[orc]` |
| Avro | `AvroFormat` | `pirn[avro]` |
| HDF5 | `Hdf5Format` | `pirn[hdf5]` |
| Zarr | `ZarrFormat` | `pirn[zarr]` |
| ONNX | `OnnxFormat` | `pirn[ml-formats]` |
| SafeTensors | `SafetensorsFormat` | `pirn[ml-formats]` |
| DICOM | `DicomFormat` | `pirn[dicom]` |
| NIfTI | `NiftiFormat` | `pirn[neuroimaging]` |
| EDF/BDF | `EdfFormat`, `BdfFormat` | `pirn[biosignals]` |
| FHIR JSON | `FhirJsonFormat` | base |
| FASTA/FASTQ | `FastaFormat`, `FastqFormat` | `pirn[genomics]` |
| BAM/SAM/CRAM | `BamFormat`, `SamFormat`, `CramFormat` | `pirn[genomics]` |
| SEG-Y | `SegyFormat` | `pirn[segy]` |
| DLIS | `DlisFormat` | `pirn[segy]` |
| GeoTIFF | `GeoTiffFormat` | `pirn[geospatial]` |
| PDF | `PdfFormat` | `pirn[document]` |
| DOCX / PPTX | `DocxFormat`, `PptxFormat` | `pirn[document]` |
| WAV / MP3 | `WavFormat`, `Mp3Format` | `pirn[audio]` |
| PNG / JPEG / TIFF | `PngFormat`, `JpegFormat`, `TiffFormat` | `pirn[image]` |
| Compressed wrapper | `CompressedFileFormat(inner=fmt, codec=...)` | base |

---

*See also: [connectors AGENTIC_USE.md](../AGENTIC_USE.md)*
