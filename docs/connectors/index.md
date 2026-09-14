# Connector Matrix

Complete reference for every file format, codec, archive wrapper, and lakehouse adapter in pirn. Use this as the definitive "what can I read/write" guide.

!!! note "Connectors are part of core, not a domain"
    The connector interfaces — file formats, codecs, archive wrappers, object stores, and lakehouse adapters — live on **core's public surface** under `pirn.connectors.*` (ADR-2). They ship with `pirn-core` (`import pirn`) and are available to every pipeline regardless of which domain packages are installed; they are not a domain and do not require `pirn_data` / `pirn_signal` / etc. to import. Concrete format classes import as e.g. `from pirn.connectors.file_formats.parquet_format import ParquetFormat`. The per-format `pip install "<package>[<extra>]"` extras below select only the heavy decode/encode library for a given format. Where a domain package declares that library, the hint names the domain package's extra (e.g. `pirn-health[health]`), exactly as the code does.

**Columns:**
- **Read** — decoding bytes → records is supported.
- **Write** — encoding records → bytes is supported. A dash (—) means read-only.
- **Streaming** — the format's `streaming` property is `True` (rows are emitted/consumed incrementally rather than buffering the full payload). Batch-only formats show —.
- **Optional Extra** — the extra named in the format's `ImportError` hint (`pip install "<package>[<extra>]"`), exactly as its `OptionalDependency.require(...)` call declares it — usually `pirn-core[<extra>]`, or a domain package such as `pirn-health[health]`. "none" means the format works on a base `pirn-core` install.

---

## Universal Tabular

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| CSV | `CsvFormat` | ✓ | ✓ | ✓ | none | stdlib `csv`; configurable delimiter, quote char, encoding, header mode. |
| TSV | `TsvFormat` | ✓ | ✓ | ✓ | none | Tab-delimited; thin wrapper over `CsvFormat` with `delimiter="\t"`. |
| JSON | `JsonFormat` | ✓ | ✓ | ✓ | none | One JSON object per file; stdlib `json`. |
| JSON Lines | `JsonlFormat` | ✓ | ✓ | ✓ | none | One JSON object per line; stdlib `json`. Suitable for large files. |
| Apache Parquet | `ParquetFormat` | ✓ | ✓ | ✓ | `pirn-core[parquet]` | Backed by `pyarrow.parquet`. Configurable compression and row-group size. |
| Apache ORC | `OrcFormat` | ✓ | ✓ | — | `pirn-core[orc]` | Backed by `pyarrow.orc`. |
| Apache Avro | `AvroFormat` | ✓ | ✓ | — | `pirn-core[avro]` | Backed by `fastavro`. Schema embedded in file. |
| Apache Arrow IPC | `ArrowIpcFormat` | ✓ | ✓ | ✓ | `pirn-core[arrow]` | Arrow IPC stream format (`pyarrow`). Zero-copy for downstream Arrow consumers. |
| Apache Feather v2 | `FeatherFormat` | ✓ | ✓ | — | `pirn-core[feather]` | Backed by `pyarrow.feather`. Equivalent to Arrow IPC file format. |
| Microsoft Excel XLSX | `XlsxFormat` | ✓ | ✓ | — | `pirn-core[xlsx]` | Read via `openpyxl` (macro-safe, values not formulas); write via `xlsxwriter`. |
| OpenDocument Spreadsheet ODS | `OdsFormat` | ✓ | ✓ | — | `pirn-core[ods]` | Backed by `odfpy`. |

---

## Scientific / Numerical

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| HDF5 | `Hdf5Format` | ✓ | ✓ | — | `pirn-core[hdf5]` | Backed by `h5py`. Hierarchical datasets. |
| Zarr | `ZarrFormat` | ✓ | ✓ | — | `pirn-core[zarr]` | Backed by `zarr`. N-dimensional chunked arrays. |
| MATLAB .mat | `MatlabMatFormat` | ✓ | ✓ | — | `pirn-core[matlab]` | Backed by `scipy.io`. MAT v5/v7.3 support. |
| NetCDF classic | `NetcdfFormat` | ✓ | ✓ | — | `pirn-core[netcdf]` | Backed by `netCDF4`. CF conventions. |
| NetCDF4 | `Netcdf4Format` | ✓ | ✓ | — | `pirn-core[netcdf]` | NetCDF4 / HDF5 backend via `netCDF4`. |
| NumPy .npy | `NumpyNpyFormat` | ✓ | ✓ | — | none | Single-array `.npy` files; backed by `numpy`. |
| NumPy .npz | `NumpyNpzFormat` | ✓ | ✓ | — | none | Multi-array `.npz` archives; backed by `numpy`. |

---

## Astronomy / Physics

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| FITS | `FitsFormat` | ✓ | ✓ | — | `pirn-core[fits]` | Backed by `astropy.io.fits`. Table HDUs emitted as records. |
| ASDF | `AsdfFormat` | ✓ | ✓ | — | `pirn-core[asdf]` | Advanced Scientific Data Format; backed by `asdf`. |
| MzML (mass spec) | `MzmlFormat` | ✓ | ✓ | — | `pirn-core[pyteomics]` (read), `pirn-core[html]` (write, `lxml`) | HUPO-PSI mass spectrometry XML; backed by `pyteomics`. |
| ROOT (particle physics) | `RootFormat` | ✓ | — | — | `pirn-core[root]` | CERN ROOT TTrees via `uproot`. Write not supported. |

---

## Documents

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| PDF | `PdfFormat` | ✓ | ✓ | — | `pirn-core[pdf]` | Read via `pypdf`; write via `reportlab`. |
| DOCX | `DocxFormat` | ✓ | ✓ | — | `pirn-core[docx]` | Backed by `python-docx`. |
| PPTX | `PptxFormat` | ✓ | ✓ | — | `pirn-core[pptx]` | Backed by `python-pptx`. Slide text extracted as records on read. |
| HTML | `HtmlFormat` | ✓ | ✓ | — | `pirn-core[html]` | Read via `beautifulsoup4`+`lxml` (tag stripping); write produces basic HTML. |
| Markdown | `MarkdownFormat` | ✓ | ✓ | ✓ | `pirn-core[markdown]` | Read via `markdown-it-py` (`markdown` when `split_on="file"`); write needs no library. |
| EPUB | `EpubFormat` | ✓ | ✓ | — | `pirn-core[epub]` | Backed by `ebooklib`. |
| RTF | `RtfFormat` | ✓ | ✓ | — | `pirn-core[rtf]` | Backed by `striprtf`. |
| Plain text | `PlainTextFormat` | ✓ | ✓ | ✓ | none | One record per line; stdlib only. |

---

## Genomics

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| FASTA | `FastaFormat` | ✓ | ✓ | ✓ | none | Stdlib parse path. |
| FASTQ | `FastqFormat` | ✓ | ✓ | ✓ | none | Stdlib parse path. Records: `seq_id`, `description`, `sequence`, `quality`. |
| VCF | `VcfFormat` | ✓ | ✓ | ✓ | none | Stdlib parse path. Variant call format. |
| BCF | `BcfFormat` | ✓ | ✓ | — | `pirn-health[genomics]` | Binary VCF; backed by `pysam`. |
| BAM | `BamFormat` | ✓ | ✓ | — | `pirn-health[genomics]` | Binary Alignment Map; backed by `pysam`. |
| CRAM | `CramFormat` | ✓ | ✓ | — | `pirn-health[genomics]` | Reference-compressed alignment; backed by `pysam`. |
| SAM | `SamFormat` | ✓ | ✓ | ✓ | `pirn-health[genomics]` | Sequence Alignment Map text format; backed by `pysam`. |

---

## Geospatial

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| Shapefile | `ShapefileFormat` | ✓ | ✓ | — | `pirn-core[shapefile]` | Backed by `pyshp`. Emits GeoJSON-style geometry dicts. |
| GeoJSON | `GeoJsonFormat` | ✓ | ✓ | ✓ | none | Stdlib `json`. Feature collections. |
| KML | `KmlFormat` | ✓ | ✓ | — | `pirn-core[kml]` | Backed by `simplekml`+`lxml`. |
| GeoTIFF | `GeotiffFormat` | ✓ | ✓ | — | `pirn-core[geotiff]` | Backed by `rasterio`. Raster data with CRS metadata. |
| GeoPackage | `GeopackageFormat` | ✓ | ✓ | — | `pirn-core[geopackage]` | Backed by `fiona`. SQLite-backed vector layers. |

---

## ML Artifacts

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| ONNX | `OnnxFormat` | ✓ | ✓ | — | `pirn-core[onnx]` | Backed by `onnx`. Model graph serialisation. |
| SafeTensors | `SafetensorsFormat` | ✓ | ✓ | — | `pirn-core[safetensors]` | Backed by `safetensors`+`numpy`. Memory-safe tensor storage. |
| Joblib | `JoblibFormat` | ✓ | ✓ | — | `pirn-core[joblib]` | scikit-learn pipeline serialisation via `joblib`. |
| PyTorch (.pt/.pth) | `PytorchFormat` | ✓ | ✓ | — | `pirn-core[pytorch]` | Backed by `torch.save` / `torch.load`. |
| TensorFlow SavedModel | `TfSavedModelFormat` | ✓ | ✓ | — | `pirn-core[tensorflow]` | Backed by `tensorflow`. Directory-style format serialised to bytes. |
| TFLite | `TfliteFormat` | ✓ | ✓ | — | `pirn-core[tflite]` (falls back to `pirn-core[tensorflow]`) | Backed by `ai-edge-litert`, then `tflite-runtime`, then `tensorflow.lite`. |
| GGUF | `GgufFormat` | ✓ | ✓ | — | `pirn-core[gguf]` | GGML Unified Format for quantised LLMs; backed by `gguf`. |

---

## Images

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| PNG | `PngFormat` | ✓ | ✓ | — | `pirn-core[image]` | Backed by `Pillow`. |
| JPEG | `JpegFormat` | ✓ | ✓ | — | `pirn-core[image]` | Backed by `Pillow`. |
| WebP | `WebpFormat` | ✓ | ✓ | — | `pirn-core[image]` | Backed by `Pillow`. |
| HEIC | `HeicFormat` | ✓ | ✓ | — | `pirn-core[heic]` | Backed by `pillow-heif`. |
| TIFF (multi-page) | `TiffFormat` | ✓ | ✓ | — | `pirn-core[tiff]` | Backed by `tifffile`. Multi-page TIFF; each page is one record. |

---

## Healthcare — Imaging

| Format | Class | Read | Write | Streaming | Optional Extra | PHI Safety |
|--------|-------|------|-------|-----------|----------------|-----------|
| DICOM | `DicomFormat` | ✓ | ✓ | — | `pirn-health[health]` | `PatientID` hashed SHA-256 → `patient_id_hash`; `PatientName`, `PatientBirthDate`, `PatientAddress` dropped from `metadata`. |
| Whole-slide imaging (OpenSlide) | `OpenSlideFormat` | ✓ | — | — | `pirn-health[health]` + OpenSlide C library | Read-only. Supports SVS, NDPI, SCN, pyramidal TIFF. |
| NIfTI | `NiftiFormat` | ✓ | ✓ | — | `pirn-health[health]` | Backed by `nibabel`. Neuroimaging. |

---

## Healthcare — Clinical

| Format | Class | Read | Write | Streaming | Optional Extra | PHI Safety |
|--------|-------|------|-------|-----------|----------------|-----------|
| HL7 v2 | `Hl7v2Format` | ✓ | ✓ | — | `pirn-core[hl7]` | PID.3/5/7/11/18/19/20 replaced with `[REDACTED]`. |
| FHIR JSON | `FhirJsonFormat` | ✓ | ✓ | — | `pirn-health[health]` | PHI identifiers sanitised per HIPAA safe-harbour. |
| FHIR XML | `FhirXmlFormat` | ✓ | ✓ | — | `pirn-health[health]`, `pirn-core[html]` (write, `lxml`) | PHI identifiers sanitised per HIPAA safe-harbour. |
| CDA XML (HL7 CDA R2) | `CdaXmlFormat` | ✓ | ✓ | — | `pirn-health[health]` (read), `pirn-core[html]` (write, `lxml`) | PHI stripped before emission. |
| Define-XML (CDISC) | `DefineXmlFormat` | ✓ | ✓ | — | `pirn-health[health]` (read), `pirn-core[html]` (write, `lxml`) | Metadata/study-design format; no patient PHI in structure. |
| SDTM XPT (SAS transport) | `SdtmXptFormat` | ✓ | ✓ | — | `pirn-core[spss]`, `pirn-data[data]` (write, `pandas`) | Clinical trial submission format; backed by `pyreadstat`. |

---

## Healthcare — Biosignal

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| EDF | `EdfFormat` | ✓ | ✓ | — | `pirn-health[health]` | European Data Format physiological signals; backed by `pyedflib`. |
| EDF+ | `EdfPlusFormat` | ✓ | ✓ | — | `pirn-health[health]` | EDF+ with annotations; backed by `pyedflib`. |
| BDF | `BdfFormat` | ✓ | ✓ | — | `pirn-health[health]` | 24-bit BioSemi Data Format; backed by `pyedflib` (`FILETYPE_BDF`). |
| BrainVision | `BrainVisionFormat` | ✓ | ✓ | — | `pirn-health[health]` | BrainProducts BrainVision format; backed by `mne`. |
| BIDS dataset | `BidsDatasetFormat` | ✓ | ✓ | — | none (`pirn-core[bids]` enables optional layout validation) | Brain Imaging Data Structure (zip bundle); `pybids` used for layout validation when installed. |

---

## Audio

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| WAV | `WavFormat` | ✓ | ✓ | — | none | Backed by stdlib `wave`; no optional dependencies. |
| MP3 | `Mp3Format` | ✓ | ✓ | — | `pirn-core[audio]` + ffmpeg | Decode via `pydub`; ffmpeg required for encode. |
| AAC | `AacFormat` | ✓ | ✓ | — | `pirn-core[audio]` + ffmpeg | Decode via `pydub`; ffmpeg required. |
| OGG | `OggFormat` | ✓ | ✓ | — | `pirn-core[audio]` | Vorbis streams via `soundfile`. |
| FLAC | `FlacFormat` | ✓ | ✓ | — | `pirn-core[audio]` | Backed by `soundfile`. |
| M4A | `M4aFormat` | ✓ | ✓ | — | `pirn-core[audio]` + ffmpeg | AAC in MPEG-4 container; ffmpeg required. |

---

## Oil & Gas

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| SEG-Y (seismic) | `SegyFormat` | ✓ | ✓ | — | `pirn-oilgas[oilgas]` | Backed by `segyio`. Traces emitted as records. |
| SEG-D (field tape) | `SegdFormat` | ✓ | — | — | none | Read-only field acquisition format. |
| DLIS (well logs) | `DlisFormat` | ✓ | — | — | `pirn-core[dlis]` | Backed by `dlisio`. Write not supported upstream. |
| LAS (ASCII well logs) | `LasFormat` | ✓ | ✓ | — | `pirn-oilgas[oilgas]` | Backed by `lasio`. |
| WITSML | `WitsmlFormat` | ✓ | ✓ | — | `pirn-oilgas[oilgas]` (read), `pirn-core[html]` (write, `lxml`) | XML-based real-time drilling data. |
| PRODML | `ProdmlFormat` | ✓ | ✓ | — | `pirn-oilgas[oilgas]` (read), `pirn-core[html]` (write, `lxml`) | XML-based production data. |
| RESQML | `ResqmlFormat` | ✓ | ✓ | — | `pirn-oilgas[oilgas]` (read), `pirn-core[html]` (write, `lxml`) | Subsurface reservoir model exchange format. |

---

## Weather / Atmospheric

| Format | Class | Read | Write | Streaming | Optional Extra | Notes |
|--------|-------|------|-------|-----------|----------------|-------|
| GRIB | `GribFormat` | ✓ | — | — | `pirn-core[grib]` | Backed by `cfgrib`/`eccodes`. Read-only — GRIB encoding is handled upstream by NWP systems. |

---

## Compression Codecs

Codecs are not standalone `FileFormat` instances. Wrap any format using `CompressedFileFormat`.

```python
from pirn.connectors.file_formats.compressed_file_format import CompressedFileFormat
from pirn.connectors.file_formats.csv_format import CsvFormat

csv_gz = CompressedFileFormat(CsvFormat(), codec="gzip")
```

| Codec name | Class | Optional Extra | Notes |
|-----------|-------|----------------|-------|
| `"gzip"` | `GzipCodec` | none | stdlib `gzip`; always available. |
| `"bzip2"` | `Bzip2Codec` | none | stdlib `bz2`; always available. |
| `"zstd"` | `ZstdCodec` | `pirn-core[zstd]` | Backed by `zstandard`. |
| `"snappy"` | `SnappyCodec` | `pirn-core[snappy]` | Backed by `python-snappy`. |
| `"lz4"` | `Lz4Codec` | `pirn-core[lz4]` | Backed by `lz4`. |

The resulting `CompressedFileFormat.name` is `"{inner.name}+{codec}"`, e.g. `"parquet+zstd"` or `"csv+gzip"`. The `streaming` property mirrors the inner format's value.

---

## Archive Wrappers

`ArchiveFileFormat` wraps any `FileFormat` to decode/encode multi-file archives. Records are tagged with `{"_archive_member": "<member path>", ...original fields...}`.

```python
from pirn.connectors.file_formats.archive_file_format import ArchiveFileFormat
from pirn.connectors.file_formats.parquet_format import ParquetFormat

archive = ArchiveFileFormat(ParquetFormat(), archive_type="tar.gz")
```

| Archive type | Extra | Notes |
|-------------|-------|-------|
| `"tar"` | none | Plain uncompressed tar. |
| `"tar.gz"` | none | gzip-compressed tar; stdlib. |
| `"tar.bz2"` | none | bzip2-compressed tar; stdlib. |
| `"tar.zst"` | `pirn-core[zstd]` | zstd-compressed tar; requires `zstandard`. |
| `"zip"` | none | ZIP archive; stdlib `zipfile`. |

`ArchiveFileFormat.streaming` is always `False` — archives must be fully buffered. `ArchiveFileFormat.name` is `"{archive_type}({inner.name})"`, e.g. `"tar.gz(csv)"`.

---

## Lakehouse Table Adapters

Lakehouse adapters implement the `LakehouseTable` interface and are used with `LakehouseTableSource` / `LakehouseTableSink` knots rather than `FileSource` / `FileSink`.

| Adapter | Class | Scan | Append | Overwrite | Merge | Time-travel | Optional Extra |
|---------|-------|------|--------|-----------|-------|-------------|----------------|
| Delta Lake | `DeltaTable` | ✓ | ✓ | ✓ (full or partition predicate) | ✓ | ✓ (`snapshot_id` or `as_of_timestamp`) | `pirn-data[delta]`, `pirn-data[data]` (`pyarrow`) |
| Apache Iceberg | `IcebergTable` | ✓ | ✓ | ✓ | — (NotImplementedError; use Java writer) | ✓ (`snapshot_id` or `as_of_timestamp`) | `pirn-data[iceberg]`, `pirn-data[data]` (`pyarrow`) |
| Apache Hudi | `HudiTable` | ✓ | — | — | — | ✓ (read path only) | none (`pirn-data[hudi]` is a no-op marker; reads via pyarrow) |

**See also:** [Data Domain — Lakehouse](../domains/data.md#lakehouse), [Contributing — Domain Knots](../contributing/domain-knots.md)
