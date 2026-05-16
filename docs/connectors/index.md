# Connector Matrix

Complete reference for every file format, codec, archive wrapper, and lakehouse adapter in pirn. Use this as the definitive "what can I read/write" guide.

**Columns:**
- **Read** — decoding bytes → records is supported.
- **Write** — encoding records → bytes is supported. A dash (—) means read-only.
- **Streaming** — the format's `streaming` property is `True` (rows are emitted/consumed incrementally rather than buffering the full payload). Batch-only formats show —.
- **Optional Extra** — the `pip install pirn[<extra>]` flag required. "none" means the format works on a base pirn install.

---

## Universal Tabular

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| CSV | `CsvFormat` | ✓ | ✓ | ✓ | none | stdlib `csv`; configurable delimiter, quote char, encoding, header mode. |
| TSV | `TsvFormat` | ✓ | ✓ | ✓ | none | Tab-delimited; thin wrapper over `CsvFormat` with `delimiter="\t"`. |
| JSON | `JsonFormat` | ✓ | ✓ | ✓ | none | One JSON object per file; stdlib `json`. |
| JSON Lines | `JsonlFormat` | ✓ | ✓ | ✓ | none | One JSON object per line; stdlib `json`. Suitable for large files. |
| Apache Parquet | `ParquetFormat` | ✓ | ✓ | ✓ | `pirn[data]` | Backed by `pyarrow.parquet`. Configurable compression and row-group size. |
| Apache ORC | `OrcFormat` | ✓ | ✓ | — | `pirn[orc]` | Backed by `pyarrow.orc`. |
| Apache Avro | `AvroFormat` | ✓ | ✓ | — | `pirn[avro]` | Backed by `fastavro`. Schema embedded in file. |
| Apache Arrow IPC | `ArrowIpcFormat` | ✓ | ✓ | ✓ | `pirn[data]` | Arrow IPC stream format (`pyarrow`). Zero-copy for downstream Arrow consumers. |
| Apache Feather v2 | `FeatherFormat` | ✓ | ✓ | — | `pirn[feather]` | Backed by `pyarrow.feather`. Equivalent to Arrow IPC file format. |
| Microsoft Excel XLSX | `XlsxFormat` | ✓ | ✓ | — | `pirn[xlsx]` | Read via `openpyxl` (macro-safe, values not formulas); write via `xlsxwriter`. |
| OpenDocument Spreadsheet ODS | `OdsFormat` | ✓ | ✓ | — | `pirn[ods]` | Backed by `odfpy`. |

---

## Scientific / Numerical

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| HDF5 | `Hdf5Format` | ✓ | ✓ | — | `pirn[hdf5]` | Backed by `h5py`. Hierarchical datasets. |
| Zarr | `ZarrFormat` | ✓ | ✓ | — | `pirn[zarr]` | Backed by `zarr`. N-dimensional chunked arrays. |
| MATLAB .mat | `MatlabMatFormat` | ✓ | ✓ | — | `pirn[matlab]` | Backed by `scipy.io`. MAT v5/v7.3 support. |
| NetCDF classic | `NetcdfFormat` | ✓ | ✓ | — | `pirn[netcdf]` | Backed by `netCDF4`. CF conventions. |
| NetCDF4 | `Netcdf4Format` | ✓ | ✓ | — | `pirn[netcdf]` | NetCDF4 / HDF5 backend via `netCDF4`. |
| NumPy .npy | `NumpyNpyFormat` | ✓ | ✓ | — | `pirn[ml]` | Single-array `.npy` files; backed by `numpy`. |
| NumPy .npz | `NumpyNpzFormat` | ✓ | ✓ | — | `pirn[ml]` | Multi-array `.npz` archives; backed by `numpy`. |

---

## Astronomy / Physics

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| FITS | `FitsFormat` | ✓ | ✓ | — | `pirn[astronomy]` | Backed by `astropy.io.fits`. Table HDUs emitted as records. |
| ASDF | `AsdfFormat` | ✓ | ✓ | — | `pirn[astronomy]` | Advanced Scientific Data Format; backed by `asdf`. |
| MzML (mass spec) | `MzmlFormat` | ✓ | ✓ | — | `pirn[physics]` | HUPO-PSI mass spectrometry XML; backed by `pyteomics`. |
| ROOT (particle physics) | `RootFormat` | ✓ | — | — | `pirn[physics]` | CERN ROOT TTrees via `uproot`. Write not supported. |

---

## Documents

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| PDF | `PdfFormat` | ✓ | ✓ | — | `pirn[pdf]` | Read via `pypdf`; write via `reportlab`. |
| DOCX | `DocxFormat` | ✓ | ✓ | — | `pirn[docx]` | Backed by `python-docx`. |
| PPTX | `PptxFormat` | ✓ | ✓ | — | `pirn[pptx]` | Backed by `python-pptx`. Slide text extracted as records on read. |
| HTML | `HtmlFormat` | ✓ | ✓ | — | `pirn[html]` | Read via `beautifulsoup4`+`lxml` (tag stripping); write produces basic HTML. |
| Markdown | `MarkdownFormat` | ✓ | ✓ | ✓ | `pirn[markdown]` | Backed by `markdown-it-py` on read, `markdown` on write. |
| EPUB | `EpubFormat` | ✓ | ✓ | — | `pirn[epub]` | Backed by `ebooklib`. |
| RTF | `RtfFormat` | ✓ | ✓ | — | `pirn[rtf]` | Backed by `striprtf`. |
| Plain text | `PlainTextFormat` | ✓ | ✓ | ✓ | none | One record per line; stdlib only. |

---

## Genomics

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| FASTA | `FastaFormat` | ✓ | ✓ | ✓ | `pirn[genomics]` | Backed by `pyfaidx` for indexed random access. |
| FASTQ | `FastqFormat` | ✓ | ✓ | ✓ | none | Stdlib parse path; `pirn[genomics]` for indexed reads. Records: `seq_id`, `description`, `sequence`, `quality`. |
| VCF | `VcfFormat` | ✓ | ✓ | ✓ | `pirn[genomics]` | Backed by `pysam`. Variant call format. |
| BCF | `BcfFormat` | ✓ | ✓ | — | `pirn[genomics]` | Binary VCF; backed by `pysam`. |
| BAM | `BamFormat` | ✓ | ✓ | — | `pirn[genomics]` | Binary Alignment Map; backed by `pysam`. |
| CRAM | `CramFormat` | ✓ | ✓ | — | `pirn[genomics]` | Reference-compressed alignment; backed by `pysam`. |
| SAM | `SamFormat` | ✓ | ✓ | ✓ | `pirn[genomics]` | Sequence Alignment Map text format; backed by `pysam`. |

---

## Geospatial

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| Shapefile | `ShapefileFormat` | ✓ | ✓ | — | `pirn[shapefile]` | Backed by `pyshp`. Emits GeoJSON-style geometry dicts. |
| GeoJSON | `GeojsonFormat` | ✓ | ✓ | ✓ | `pirn[geojson]` | Backed by `geojson`. Feature collections. |
| KML | `KmlFormat` | ✓ | ✓ | — | `pirn[kml]` | Backed by `simplekml`+`lxml`. |
| GeoTIFF | `GeotiffFormat` | ✓ | ✓ | — | `pirn[geotiff]` | Backed by `rasterio`. Raster data with CRS metadata. |
| GeoPackage | `GeopackageFormat` | ✓ | ✓ | — | `pirn[geopackage]` | Backed by `fiona`. SQLite-backed vector layers. |

---

## ML Artifacts

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| ONNX | `OnnxFormat` | ✓ | ✓ | — | `pirn[onnx]` | Backed by `onnx`. Model graph serialisation. |
| SafeTensors | `SafetensorsFormat` | ✓ | ✓ | — | `pirn[safetensors]` | Backed by `safetensors`+`numpy`. Memory-safe tensor storage. |
| Joblib | `JoblibFormat` | ✓ | ✓ | — | `pirn[joblib]` | scikit-learn pipeline serialisation via `joblib`. |
| PyTorch (.pt/.pth) | `PytorchFormat` | ✓ | ✓ | — | `pirn[pytorch]` | Backed by `torch.save` / `torch.load`. |
| TensorFlow SavedModel | `TfSavedModelFormat` | ✓ | ✓ | — | `pirn[tensorflow]` | Backed by `tensorflow`. Directory-style format serialised to bytes. |
| TFLite | `TfliteFormat` | ✓ | ✓ | — | `pirn[tflite]` | Backed by `tflite-runtime` or falls back to `pirn[tensorflow]`. |
| GGUF | `GgufFormat` | ✓ | ✓ | — | `pirn[gguf]` | GGML Unified Format for quantised LLMs; backed by `gguf`. |

---

## Images

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| PNG | `PngFormat` | ✓ | ✓ | — | `pirn[image]` | Backed by `Pillow`. |
| JPEG | `JpegFormat` | ✓ | ✓ | — | `pirn[image]` | Backed by `Pillow`. |
| WebP | `WebpFormat` | ✓ | ✓ | — | `pirn[image]` | Backed by `Pillow`. |
| HEIC | `HeicFormat` | ✓ | ✓ | — | `pirn[heic]` | Backed by `pillow-heif`. |
| TIFF (multi-page) | `TiffFormat` | ✓ | ✓ | — | `pirn[tiff]` | Backed by `tifffile`+`Pillow`. Multi-page TIFF; each page is one record. |

---

## Healthcare — Imaging

| Format | Class | Read | Write | Streaming | Optional Extra | PHI Safety |
|--------|-------|------|-------|-----------|----------------|-----------|
| DICOM | `DicomFormat` | ✓ | ✓ | — | `pirn[dicom]` | `PatientID` hashed SHA-256 → `patient_id_hash`; `PatientName`, `PatientBirthDate`, `PatientAddress` dropped from `metadata`. |
| Whole-slide imaging (OpenSlide) | `OpenSlideFormat` | ✓ | — | — | `pirn[health]` + OpenSlide C library | Read-only. Supports SVS, NDPI, SCN, pyramidal TIFF. |
| NIfTI | `NiftiFormat` | ✓ | ✓ | — | `pirn[health]` | Backed by `nibabel`. Neuroimaging. |

---

## Healthcare — Clinical

| Format | Class | Read | Write | Streaming | Optional Extra | PHI Safety |
|--------|-------|------|-------|-----------|----------------|-----------|
| HL7 v2 | `Hl7v2Format` | ✓ | ✓ | — | `pirn[health]` | PID.3/5/7/11/18/19/20 replaced with `[REDACTED]`. |
| FHIR JSON | `FhirJsonFormat` | ✓ | ✓ | — | `pirn[health]` | PHI identifiers sanitised per HIPAA safe-harbour. |
| FHIR XML | `FhirXmlFormat` | ✓ | ✓ | — | `pirn[health]` | PHI identifiers sanitised per HIPAA safe-harbour. |
| CDA XML (HL7 CDA R2) | `CdaXmlFormat` | ✓ | ✓ | — | `pirn[health]` | PHI stripped before emission. |
| Define-XML (CDISC) | `DefineXmlFormat` | ✓ | ✓ | — | `pirn[health]` | Metadata/study-design format; no patient PHI in structure. |
| SDTM XPT (SAS transport) | `SdtmXptFormat` | ✓ | ✓ | — | `pirn[health]` | Clinical trial submission format; backed by `pyreadstat`. |

---

## Healthcare — Biosignal

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| EDF | `EdfFormat` | ✓ | ✓ | — | `pirn[health]` | European Data Format physiological signals; backed by `pyedflib`. |
| EDF+ | `EdfPlusFormat` | ✓ | ✓ | — | `pirn[health]` | EDF+ with annotations; backed by `pyedflib`. |
| BDF | `BdfFormat` | ✓ | ✓ | — | `pirn[health]` | 24-bit BioSemi Data Format; backed by `pyedflib` (`FILETYPE_BDF`). |
| BrainVision | `BrainvisionFormat` | ✓ | ✓ | — | `pirn[health]` | BrainProducts BrainVision format; backed by `mne`. |
| BIDS dataset | `BidsDatasetFormat` | ✓ | ✓ | — | `pirn[health]` | Brain Imaging Data Structure (zip bundle); `pybids` used for layout validation when installed. |

---

## Audio

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| WAV | `WavFormat` | ✓ | ✓ | — | `pirn[audio]` | Backed by stdlib `wave`; no optional dependencies. |
| MP3 | `Mp3Format` | ✓ | ✓ | — | `pirn[audio]` + ffmpeg | Decode via `pydub`; ffmpeg required for encode. |
| AAC | `AacFormat` | ✓ | ✓ | — | `pirn[audio]` + ffmpeg | Decode via `pydub`; ffmpeg required. |
| OGG | `OggFormat` | ✓ | ✓ | — | `pirn[audio]` | Vorbis streams via `soundfile`. |
| FLAC | `FlacFormat` | ✓ | ✓ | — | `pirn[audio]` | Backed by `soundfile`. |
| M4A | `M4aFormat` | ✓ | ✓ | — | `pirn[audio]` + ffmpeg | AAC in MPEG-4 container; ffmpeg required. |

---

## Oil & Gas

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| SEG-Y (seismic) | `SegyFormat` | ✓ | ✓ | — | `pirn[oilgas]` | Backed by `segyio`. Traces emitted as records. |
| SEG-D (field tape) | `SegdFormat` | ✓ | — | — | `pirn[oilgas]` | Read-only field acquisition format. |
| DLIS (well logs) | `DlisFormat` | ✓ | — | — | `pirn[oilgas]` | Backed by `dlisio`. Write not supported upstream. |
| LAS (ASCII well logs) | `LasFormat` | ✓ | ✓ | — | `pirn[oilgas]` | Backed by `lasio`. |
| WITSML | `WitsmlFormat` | ✓ | ✓ | — | `pirn[oilgas]` | XML-based real-time drilling data. |
| PRODML | `ProdmlFormat` | ✓ | ✓ | — | `pirn[oilgas]` | XML-based production data. |
| RESQML | `ResqmlFormat` | ✓ | ✓ | — | `pirn[oilgas]` | Subsurface reservoir model exchange format. |

---

## Weather / Atmospheric

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| GRIB | `GribFormat` | ✓ | — | — | `pirn[weather]` | Backed by `cfgrib`/`eccodes`. Read-only — GRIB encoding is handled upstream by NWP systems. |

---

## Compression Codecs

Codecs are not standalone `FileFormat` instances. Wrap any format using `CompressedFileFormat`.

```python
from pirn.domains.connectors.file_formats.compressed_file_format import CompressedFileFormat
from pirn.domains.connectors.file_formats.csv_format import CsvFormat

csv_gz = CompressedFileFormat(CsvFormat(), codec="gzip")
```

| Codec name | Class | Optional Extra | Notes |
|-----------|-------|----------------|-------|
| `"gzip"` | `GzipCodec` | none | stdlib `gzip`; always available. |
| `"bzip2"` | `Bzip2Codec` | none | stdlib `bz2`; always available. |
| `"zstd"` | `ZstdCodec` | `pirn[zstd]` | Backed by `zstandard`. |
| `"snappy"` | `SnappyCodec` | `pirn[snappy]` | Backed by `python-snappy`. |
| `"lz4"` | `Lz4Codec` | `pirn[lz4]` | Backed by `lz4`. |

The resulting `CompressedFileFormat.name` is `"{inner.name}+{codec}"`, e.g. `"parquet+zstd"` or `"csv+gzip"`. The `streaming` property mirrors the inner format's value.

---

## Archive Wrappers

`ArchiveFileFormat` wraps any `FileFormat` to decode/encode multi-file archives. Records are tagged with `{"_archive_member": "<member path>", ...original fields...}`.

```python
from pirn.domains.connectors.file_formats.archive_file_format import ArchiveFileFormat
from pirn.domains.connectors.file_formats.parquet_format import ParquetFormat

archive = ArchiveFileFormat(ParquetFormat(), archive_type="tar.gz")
```

| Archive type | Extra | Notes |
|-------------|-------|-------|
| `"tar"` | none | Plain uncompressed tar. |
| `"tar.gz"` | none | gzip-compressed tar; stdlib. |
| `"tar.bz2"` | none | bzip2-compressed tar; stdlib. |
| `"tar.zst"` | `pirn[zstd]` | zstd-compressed tar; requires `zstandard`. |
| `"zip"` | none | ZIP archive; stdlib `zipfile`. |

`ArchiveFileFormat.streaming` is always `False` — archives must be fully buffered. `ArchiveFileFormat.name` is `"{archive_type}({inner.name})"`, e.g. `"tar.gz(csv)"`.

---

## Lakehouse Table Adapters

Lakehouse adapters implement the `LakehouseTable` interface and are used with `LakehouseTableSource` / `LakehouseTableSink` knots rather than `FileSource` / `FileSink`.

| Adapter | Class | Scan | Append | Overwrite | Merge | Time-travel | Optional Extra |
|---------|-------|------|--------|-----------|-------|-------------|----------------|
| Delta Lake | `DeltaTable` | ✓ | ✓ | ✓ (full or partition predicate) | ✓ | ✓ (`snapshot_id` or `as_of_timestamp`) | `pirn[delta]` |
| Apache Iceberg | `IcebergTable` | ✓ | ✓ | ✓ | — (NotImplementedError; use Java writer) | ✓ (`snapshot_id` or `as_of_timestamp`) | `pirn[iceberg]` |
| Apache Hudi | `HudiTable` | ✓ | — | — | — | ✓ (read path only) | none (`pirn[hudi]` is a no-op; reads via pyarrow) |

**See also:** [Data Domain — Lakehouse](../domains/data.md#lakehouse), [Contributing — Domain Knots](../contributing/domain-knots.md)
