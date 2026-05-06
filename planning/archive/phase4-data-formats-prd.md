# Phase 4 — Data Format Support PRD

**Status:** Design.
**Date:** 2026-05-01.
**Owner:** pirn data domain.

## Problem

Today pirn handles file-format I/O fragmentarily:

- `FileFormat` interface exists at `pirn/domains/connectors/file_format.py` —
  zero concrete implementations.
- `ObjectStore` connectors (S3/GCS/Azure/Local) read/write **bytes** with
  no encoding awareness.
- Engine-specific format support exists in islands:
  - Spark Tier-3: full format catalog via `session.read.format(...).load(...)`.
  - Lance: full source + sink + bridges (Lance-specific).
  - PyArrow: in-memory adapter only — no Parquet read/write knot.
  - ML `DatasetLoader`: ad-hoc `pq.read_table` for one parquet path.
- No unified `S3 + format → DataBatch` path. Consumers have to:
  1. Read raw bytes via `ObjectStore.get`.
  2. Manually parse with `pandas.read_csv`, `pyarrow.parquet.read_table`, etc.
  3. Wrap in `DataBatch` themselves.

This blocks every downstream domain (data, agents, ml, health, signal,
oilgas) from a clean "read this format from anywhere" experience.

## Goals

1. Implement `FileFormat` for ~75 formats spanning all five domain
   libraries plus universal tabular and document handling.
2. Compose `ObjectStore × FileFormat` into reusable `FileSource` /
   `FileSink` knots.
3. Treat compression (gzip/bzip2/zstd/snappy/lz4) as transparent
   wrappers, not per-format flags.
4. Treat lakehouse table formats (Delta/Iceberg/Hudi) as a separate
   abstraction (`LakehouseTable*`) with transaction-log + schema-
   evolution semantics.
5. Each format gets an optional pyproject extra so the core install
   stays small.
6. Each format gets a unit test (round-trip) plus integration tests
   where containerisable backends exist (MinIO for S3, Azurite for
   Azure Blob, etc.).

## Non-goals

- Schema-on-read inference for arbitrary CSV / JSON. Callers supply a
  schema; pirn validates on write and exposes it on read.
- Format conversion. Read into `DataBatch` (or a typed wrapper for
  binary-payload formats) and let downstream knots transform.
- Compression-aware streaming for pure-batch formats (XLSX, PDF). The
  `BatchFileFormat` subtype declares this trade-off explicitly.

## Design

### 1. Refined `FileFormat` interface — split streaming vs batch

Current interface is purely streaming (`read: AsyncIterator[bytes] →
AsyncIterator[Any]`). That's right for Parquet / Arrow / Avro / JSONL
which can decode chunk-by-chunk. It's wrong for XLSX / PDF / HDF5 which
require full-file decode before yielding records.

**New shape:**

```python
class FileFormat:
    """Base interface — both streaming and batch implementations satisfy this."""

    @property
    def name(self) -> str: ...

    @property
    def streaming(self) -> bool:
        """True if read() can decode incrementally; False = full-file required."""
        return False

    async def read(self, body: AsyncIterator[bytes]) -> AsyncIterator[Mapping[str, Any]]: ...

    async def write(self, records: AsyncIterator[Mapping[str, Any]]) -> AsyncIterator[bytes]: ...

class StreamingFileFormat(FileFormat):
    """Marker — chunked decode is supported. Default streaming=True."""
    @property
    def streaming(self) -> bool:
        return True

class BatchFileFormat(FileFormat):
    """Whole-file decode required. read() buffers the body internally."""
    @property
    def streaming(self) -> bool:
        return False

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        """Subclasses implement full-file decode."""
        raise NotImplementedError(...)

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        """Subclasses implement full-file encode."""
        raise NotImplementedError(...)

    # read/write provided by base — buffer the iterator and call _decode_full / _encode_full.
```

Consumers can opt to special-case `streaming=False` formats (e.g.,
require seekable storage, refuse infinite streams).

### 2. Compression — `CompressedFileFormat` wrapper

```python
class CompressedFileFormat(FileFormat):
    """Wrap any FileFormat with a transparent codec.

    Supported codecs: gzip, bzip2, zstd, snappy, lz4.
    """
    def __init__(self, inner: FileFormat, codec: str): ...

    @property
    def name(self) -> str:
        return f"{self._inner.name}+{self._codec}"

    @property
    def streaming(self) -> bool:
        return self._inner.streaming  # codec is transparent
```

This composes naturally: `CompressedFileFormat(ParquetFormat(), "zstd")`
reads `data.parquet.zst`. Streaming codec wrappers (`gzip`, `zstd`)
preserve `streaming=True`; batch-only codecs would force `streaming=False`
(none of the listed five do this).

Multi-file archives (`tar`, `zip`) get a different shape:
`ArchiveFileFormat` emits `(filename, FileFormat-decoded-records)` pairs.
That's a separate concern, not a `CompressedFileFormat`.

### 3. `FileSource` / `FileSink` Knots

```python
class FileSource(Knot):
    """Compose ObjectStore.get(key) with FileFormat.read into a DataBatch."""

    def __init__(
        self,
        *,
        store: ObjectStore,
        format: FileFormat,
        key: str,
        schema: DataSchema | None = None,
        _config: KnotConfig,
    ): ...

    async def process(self, **_: Any) -> DataBatch: ...

class FileSink(Knot):
    """Compose FileFormat.write with ObjectStore.put(key)."""

    def __init__(
        self,
        *,
        batch: Knot,
        store: ObjectStore,
        format: FileFormat,
        key: str,
        _config: KnotConfig,
    ): ...

    async def process(self, batch: DataBatch, **_: Any) -> str:
        """Returns the key the data was written to."""

class DirectorySource(Knot):
    """Glob a prefix; emit one DataBatch per file. Records concatenated
    when concatenate=True."""

    def __init__(
        self,
        *,
        store: ObjectStore,
        format: FileFormat,
        prefix: str,
        concatenate: bool = False,
        _config: KnotConfig,
    ): ...
```

These live under `pirn/domains/data/sources/` and `pirn/domains/data/sinks/`.

### 4. Lakehouse table formats — separate from `FileFormat`

Delta, Iceberg, Hudi are NOT file formats. They are table specs with:
- transaction logs,
- schema evolution,
- time travel (snapshot id / timestamp queries),
- partition pruning,
- compaction.

Forcing them through `FileFormat.read(bytes → records)` loses every
distinguishing feature. Proper abstraction:

```python
class LakehouseTable:
    """Versioned, transactional table interface.

    Unlike FileFormat (single-file encode/decode), LakehouseTable
    represents a whole table with metadata, history, and write
    semantics."""

    @property
    def name(self) -> str: ...

    async def scan(
        self,
        *,
        snapshot_id: int | str | None = None,
        as_of_timestamp: datetime | None = None,
        filter: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]: ...

    async def append(self, records: AsyncIterator[Mapping[str, Any]]) -> str:
        """Write rows; return the new snapshot id."""

    async def overwrite(self, records: AsyncIterator[Mapping[str, Any]]) -> str: ...

    async def merge(
        self,
        records: AsyncIterator[Mapping[str, Any]],
        *,
        on: Sequence[str],
    ) -> str:
        """MERGE-style upsert."""

    async def history(self) -> AsyncIterator[Mapping[str, Any]]:
        """Yield commit history."""
```

Concrete implementations: `DeltaTable` (via `delta-rs`), `IcebergTable`
(via `pyiceberg`), `HudiTable` (via `hudi-python` or `pyhudi`).

`LakehouseTableSource` and `LakehouseTableSink` Knots wire these into
pirn pipelines, mirroring `FileSource` / `FileSink` shape.

### 5. Round-trip test harness

```python
# tests/unit/domains/connectors/file_formats/_format_round_trip.py

class FormatRoundTripTest:
    """Helper — every format implementation runs this against a fixture batch."""

    @staticmethod
    async def assert_round_trip(
        format: FileFormat,
        records: Sequence[Mapping[str, Any]],
    ) -> None:
        """Encode records → decode → assert equality (order-preserving)."""
        ...
```

Each format test imports `FormatRoundTripTest.assert_round_trip` and
runs it against domain-appropriate fixtures.

## Sub-package layout

```
pirn/domains/connectors/file_formats/
    __init__.py
    streaming_file_format.py        # StreamingFileFormat base
    batch_file_format.py            # BatchFileFormat base
    compressed_file_format.py       # CompressedFileFormat wrapper
    archive_file_format.py          # tar/zip multi-file wrapper

    # Universal tabular (Wave A1)
    parquet_format.py
    csv_format.py
    tsv_format.py
    json_format.py
    jsonl_format.py
    avro_format.py
    orc_format.py
    arrow_ipc_format.py
    feather_format.py
    xlsx_format.py
    ods_format.py

    # Scientific tabular (Wave A2)
    hdf5_format.py
    zarr_format.py
    numpy_npy_format.py
    numpy_npz_format.py
    matlab_mat_format.py
    netcdf_format.py

    # Compression codecs (Wave A4) — used by CompressedFileFormat
    codecs/
        gzip_codec.py
        bzip2_codec.py
        zstd_codec.py
        snappy_codec.py
        lz4_codec.py

    # Documents (Wave B1)
    pdf_format.py
    docx_format.py
    pptx_format.py
    html_format.py
    markdown_format.py
    plain_text_format.py
    epub_format.py
    rtf_format.py

    # Healthcare clinical (Wave B2)
    fhir_json_format.py
    fhir_xml_format.py
    hl7v2_format.py
    cda_xml_format.py
    define_xml_format.py
    sdtm_xpt_format.py

    # Healthcare imaging (Wave B3)
    dicom_format.py
    nifti_format.py
    bids_dataset_format.py
    open_slide_format.py
    mzml_format.py

    # Healthcare genomics (Wave B4)
    fasta_format.py
    fastq_format.py
    bam_format.py
    sam_format.py
    cram_format.py
    vcf_format.py
    bcf_format.py

    # Healthcare biosignal (Wave B5)
    edf_format.py
    edf_plus_format.py
    bdf_format.py
    brainvision_format.py

    # Signal/audio (Wave C1)
    wav_format.py
    flac_format.py
    mp3_format.py
    ogg_format.py
    aac_format.py
    m4a_format.py

    # Oil & gas (Wave C2)
    segy_format.py
    las_format.py
    dlis_format.py
    witsml_format.py
    prodml_format.py
    resqml_format.py
    segd_format.py

    # Geospatial (Wave C3)
    shapefile_format.py
    geojson_format.py
    kml_format.py
    geotiff_format.py
    geopackage_format.py

    # ML artifacts (Wave D1)
    onnx_format.py
    safetensors_format.py
    joblib_format.py
    pytorch_format.py
    tf_saved_model_format.py
    gguf_format.py
    tflite_format.py

    # Images (Wave D2)
    tiff_format.py
    png_format.py
    jpeg_format.py
    webp_format.py
    heic_format.py

    # Specialty (Wave E)
    root_format.py
    fits_format.py
    grib_format.py
    netcdf4_format.py
    asdf_format.py
```

```
pirn/domains/data/sources/
    __init__.py
    file_source.py
    directory_source.py
    api_source.py            # already planned in execution-plan
    stream_source.py         # already planned

pirn/domains/data/sinks/
    __init__.py
    file_sink.py
    data_catalog_sink.py     # already planned

pirn/domains/data/lakehouse/
    __init__.py
    lakehouse_table.py        # interface
    delta/delta_table.py
    iceberg/iceberg_table.py
    hudi/hudi_table.py
    lakehouse_table_source.py
    lakehouse_table_sink.py
```

## Wave plan

| Wave | Sub-area | Formats | Estimated agents |
|------|----------|---------|------------------|
| Foundation | interface refinement + compression layer + FileSource/Sink + Lakehouse interfaces + test harness | n/a | me directly |
| A1 | universal tabular | 11 | 3 |
| A2 | scientific tabular | 6 | 2 |
| A3 | lakehouse | 3 | 1 |
| A4 | compression codecs | 5 | 1 |
| B1 | documents | 8 | 2 |
| B2 | healthcare clinical | 6 | 2 |
| B3 | healthcare imaging | 5 | 2 |
| B4 | healthcare genomics | 7 | 2 |
| B5 | healthcare biosignal | 4 | 1 |
| C1 | signal/audio | 6 | 2 |
| C2 | oil & gas | 7 | 2 |
| C3 | geospatial | 5 | 2 |
| D1 | ML artifacts | 7 | 2 |
| D2 | images | 5 | 1 |
| E | specialty | 5 | 1 |

**Totals:** ~90 formats, ~25-30 parallel agent dispatches across the
waves. Multi-session work.

## Tests

- Per format: round-trip test (encode → decode → equality).
- Per format: schema validation test (DataSchema on read enforces type
  expectations).
- Per format: compression layer test (gzip + zstd at minimum).
- Lakehouse: snapshot read + append + merge round-trip per engine.

## Pyproject extras

Each format with non-trivial deps gets its own extra. Examples:

```toml
parquet     = ["pyarrow>=14.0"]
xlsx        = ["openpyxl>=3.1", "xlsxwriter>=3.2"]
ods         = ["odfpy>=1.4"]
hdf5        = ["h5py>=3.10"]
zarr        = ["zarr>=2.16"]
matlab      = ["scipy>=1.12"]
netcdf      = ["netcdf4>=1.6"]
delta       = ["deltalake>=0.17"]
iceberg     = ["pyiceberg>=0.6"]
hudi        = ["hudi-python>=0.1"]
zstd        = ["zstandard>=0.22"]
lz4         = ["lz4>=4.3"]
snappy      = ["python-snappy>=0.7"]
pdf         = ["pypdf>=4.0"]
docx        = ["python-docx>=1.1"]
pptx        = ["python-pptx>=0.6"]
html        = ["beautifulsoup4>=4.12", "lxml>=5.0"]
fhir        = ["fhir.resources>=7.1"]
hl7v2       = ["hl7>=0.4"]
xport       = ["pyreadstat>=1.2"]
dicom       = ["pydicom>=2.4"]
nifti       = ["nibabel>=5.2"]
openslide   = ["openslide-python>=1.3"]
mzml        = ["pyteomics>=4.7"]
genomics    = ["pyfaidx>=0.7", "pysam>=0.22"]
edf         = ["pyedflib>=0.1"]
brainvision = ["mne>=1.6"]
audio       = ["soundfile>=0.12", "librosa>=0.10"]
segy        = ["segyio>=1.9"]
las         = ["lasio>=0.31"]
dlis        = ["dlisio>=1.0"]
shapefile   = ["pyshp>=2.3"]
geojson     = ["geojson>=3.1"]
geotiff     = ["rasterio>=1.3"]
geopackage  = ["fiona>=1.9"]
onnx        = ["onnx>=1.16"]
safetensors = ["safetensors>=0.4"]
joblib      = ["joblib>=1.4"]
gguf        = ["gguf>=0.10"]
tflite      = ["tflite-runtime>=2.14"]
tiff        = ["tifffile>=2024.0"]
heic        = ["pillow-heif>=0.14"]
root        = ["uproot>=5.3"]
fits        = ["astropy>=6.0"]
grib        = ["cfgrib>=0.9"]
asdf        = ["asdf>=3.1"]
```

Convenience aggregates (`all-formats`, `all-tabular`, `all-healthcare-formats`,
etc.) bundle the typical groupings.

## Security considerations carried over from Phase 3 review

- `joblib`/`pickle`-based formats (joblib_format.py, pytorch_format.py with
  `weights_only=False`) MUST require a signer like `_CloudObjectStore`.
  Default refuses unsigned reads; opt-in via `allow_unsigned=True`.
- Format readers that load remote URLs (e.g. PDF with embedded
  references) need the same SSRF guard as `_DocumentLoader`.
- DICOM / NIfTI / OpenSlide files can be malicious — defer to upstream
  library hardening but document that pirn does not sandbox them.
- XLSX with macros — strip on read (`openpyxl read_only=True` is enough).
- XML parsers — use `defusedxml` to disable XXE / billion-laughs.

## Deferred to follow-up PRs

- Async streaming variants of batch-only formats once libraries support
  them (e.g., async XLSX is a research project).
- Format-aware partitioning (Hive-style `year=2024/month=05/day=01/`).
- Schema migration tools.
- Format conversion knots (`CsvToParquetTransform`).
