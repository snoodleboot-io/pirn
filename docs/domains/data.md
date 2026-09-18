# Data Domain

The `pirn_data` package is pirn's universal layer for reading, transforming, and writing structured data. It positions pirn as an **orchestrator**, not an engine: the heavy computational work is delegated to best-in-class libraries (Polars, PyArrow, Ibis, DuckDB, etc.), while pirn supplies the lineage, scheduling, composition, and typed knot graph around them.

---

## Install & registration

`pirn_data` is a standalone distribution. Install the base package plus only the tier engines you need:

```bash
pip install pirn-data                      # Tier-1 (DataBatch / dict) baseline
pip install 'pirn-data[data]'              # pandas + pyarrow (Tier-1 frames)
pip install 'pirn-data[polars]'            # Tier-2 Polars
pip install 'pirn-data[ibis]'              # Tier-3 push-down
pip install 'pirn-data[delta]'             # Delta Lake lakehouse adapter
pip install 'pirn-data[all-frames]'        # every Tier-2 single-machine CPU engine
pip install 'pirn-data[all-lazy]'          # every Tier-3 push-down engine
```

Available extras: `data`, `xarray`, `awkward`, `polars`, `datafusion`, `duckdb`, `modin`, `ibis`, `spark`, `dask`, `ray-data`, `pathway`, `bytewax`, `lance`, `eland`, `delta`, `iceberg`, `hudi`, `pandera`, `great-expectations`, and the `all-frames` / `all-lazy` aggregates.

**Registration (ADR-4):** `import pirn_data` self-registers the data-domain knots under `library="pirn"`, so a YAML pipeline can resolve them by bare name. In Python you import the knot classes directly (same effect). To register every installed domain at once, call `pirn.discover_installed_domains()`.

---

## Tiered Architecture

The data domain is organised into six tiers. Each tier is an independent opt-in extra; you only pay for the libraries you actually need.

| Tier | Name | Engine(s) | Extra(s) | Notes |
|------|------|-----------|----------|-------|
| **1** | Dict / DataBatch | Pure Python | `pirn-data[data]` | Always-on baseline; every record is a `dict`. |
| **2** | Native frames (CPU) | Polars, DataFusion, DuckDB, pandas+PyArrow | `pirn-data[polars]`, `pirn-data[datafusion]`, `pirn-data[duckdb]`, `pirn-data[data]` | Polars is the preferred Tier-2 engine. |
| **2-GPU** | Native frames (GPU) | cuDF | user-supplied | CUDA-only; install `cudf-cu12` directly. |
| **2.5** | Out-of-core / drop-in | Modin | `pirn-data[modin]` | Pandas-compatible, chunked on disk. |
| **3** | Push-down / lazy | Ibis, Spark, Dask, Ray Data | `pirn-data[ibis]`, `pirn-data[spark]`, `pirn-data[dask]`, `pirn-data[ray-data]` | Ibis is the preferred Tier-3 engine. Dask also ships with `pirn-core` as a core dispatcher (`pirn-core[dask]`); `pirn-data[dask]` installs the same package directly. |
| **3-stream** | Streaming dataflow | Pathway, Bytewax | `pirn-data[pathway]`, `pirn-data[bytewax]` | Requires Python < 3.14 until upstream catches up. |
| **4** | Specialised | Lance (vector), Eland (Elasticsearch) | `pirn-data[lance]`, `pirn-data[eland]` | Domain-specific columnar layouts. |

Tier-1 (`DataBatch`) is always included with `pirn-data[data]`. All higher tiers layer on top and are independent — installing `pirn-data[polars]` does not pull in Ibis.

The `pirn-data[all-frames]` convenience extra installs every Tier-2 single-machine CPU engine. The `pirn-data[all-lazy]` convenience extra installs every Tier-3 push-down engine.

### Import policy: no optional engine at import time

**No `pirn_data` module imports an optional engine at module scope.** `import pirn_data` imports every module (the registry fill), and it loads none of Polars, pandas, PyArrow, DataFusion, DuckDB, Ibis, Dask or Ray; CI's install-isolation job imports every submodule in a clean environment and fails otherwise.

Tier-engine modules (`pirn_data.frames.{engine}`, `pirn_data.lazy.{engine}`) follow one pattern:

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar

from pirn.core.annotation_import import AnnotationImport
from pirn.core.knot import Knot

if TYPE_CHECKING:
    import polars as pl


class PolarsWindowCalc(Knot):
    _annotation_imports: ClassVar[Mapping[str, AnnotationImport]] = {
        "pl": AnnotationImport("polars", extra="polars", package="pirn-data"),
    }

    async def process(self, batch: PolarsDataBatch, windows: Any, **_: Any) -> PolarsDataBatch:
        import polars as pl  # typed runtime access; the engine resolved at construction
        ...
```

* The engine is imported only under `if TYPE_CHECKING:`, for annotations.
* Every knot names the engine in `_annotation_imports`. `Knot` resolves those entries through `OptionalDependency.require` the first time the knot is constructed, so `process()` annotations that name engine types validate exactly as with an eager import, and a missing engine raises the `pip install "pirn-data[<extra>]"` hint at construction rather than at import.
* Runtime use of the engine is a plain import inside the method, which keeps it fully typed and is only reachable from a knot whose engine has already resolved.

Modules under `pirn_data.lakehouse`, `pirn_data.validation`, and `pirn_data.specialized` import their vendor SDK inside `process()` (or a helper it calls) the same way.

`pirn_data.lazy.spark` goes further: it declares no annotation imports and types `SparkDataFrame.frame` as `Any`, so even constructing a Spark knot does not pay PySpark's JVM bootstrap cost.

See the `pirn_data.frames` and `pirn_data.lazy` package docstrings for the same policy stated next to the code it governs.

**See also:** [Connectors — Format Matrix](../connectors/index.md), [Architecture Overview](../architecture/overview.md)

---

## DataBatch — the Tier-1 record type

`DataBatch` is the universal exchange currency across all tiers. It is a Pydantic-validated, immutable value object:

```python
from pirn_data.data_batch import DataBatch
from pirn_data.data_schema import DataSchema

batch = DataBatch(
    rows=({"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}),
    schema=DataSchema(),          # optional; adds column metadata
    source_uri="s3://bucket/key",
    fetched_at=datetime.now(timezone.utc),
)
```

Each row is a `Mapping[str, Any]`. The `rows` field is a `tuple` (immutable). Use `batch.with_rows(new_rows)` to produce a modified copy that carries the same `schema` and `source_uri`.

---

## Sources

Sources are knots that materialise data from external storage into `DataBatch` objects.

### FileSource

Reads a **single file** by composing an `ObjectStore` (where the bytes live) with a `FileFormat` (how to decode those bytes).

```python
from pirn_data.sources.file_source import FileSource
from pirn.connectors.file_formats.parquet_format import ParquetFormat
from pirn.backends.s3_data_store import S3DataStore

source = FileSource(
    store=S3DataStore(bucket="my-bucket"),
    format=ParquetFormat(),
    key="data/2026/events.parquet",
    schema=my_schema,           # optional
    source_uri="s3://my-bucket/data/2026/events.parquet",  # optional
    _config=KnotConfig(id="load_events"),
)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `store` | `ObjectStore` | yes | Where the bytes live (S3, GCS, Azure Blob, local, …). |
| `format` | `FileFormat` | yes | Decodes the bytes into records. |
| `key` | `str` | yes | Object key / path within the store. |
| `schema` | `DataSchema \| None` | no | Optional schema forwarded onto the `DataBatch`. |
| `source_uri` | `str \| None` | no | Lineage hint; defaults to `{StoreType}://{key}`. |

`process()` returns a single `DataBatch` with `rows` equal to every record the format decoded from the file.

### DirectorySource

Reads **every file under a prefix** and emits either one `DataBatch` per file or a single concatenated `DataBatch`.

```python
from pirn_data.sources.directory_source import DirectorySource

source = DirectorySource(
    store=S3DataStore(bucket="my-bucket"),
    format=ParquetFormat(),
    prefix="data/2026/",
    concatenate=True,           # False = tuple[DataBatch, ...]
    schema=my_schema,
    _config=KnotConfig(id="load_month"),
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `store` | `ObjectStore` | — | Where the bytes live. |
| `format` | `FileFormat` | — | Applied to every matching key. |
| `prefix` | `str` | — | Key prefix to glob. Use `""` for the root. |
| `concatenate` | `bool` | `False` | `True` → single merged `DataBatch`; `False` → `tuple[DataBatch, ...]`. |
| `schema` | `DataSchema \| None` | `None` | Optional schema forwarded onto every produced `DataBatch`. |

When `concatenate=False`, each batch's `source_uri` is `{StoreType}://{individual_key}`, preserving per-file provenance. When `concatenate=True`, per-file lineage is collapsed; the `source_uri` becomes `{StoreType}://{prefix}*`.

**See also:** [ObjectStore Backends](../guides/backends.md#datastore), [File Formats](../connectors/index.md)

---

## Sinks

Sinks are knots that persist a `DataBatch` to external storage.

### FileSink

Encodes a `DataBatch` and writes the bytes to an `ObjectStore`.

```python
from pirn_data.sinks.file_sink import FileSink
from pirn.connectors.file_formats.parquet_format import ParquetFormat

sink = FileSink(
    batch=transform_knot,
    store=S3DataStore(bucket="my-bucket"),
    format=ParquetFormat(compression="zstd"),
    key="output/2026/result.parquet",
    _config=KnotConfig(id="write_result"),
)
```

`process(batch)` encodes all rows via the format's `write()` method, concatenates the resulting byte chunks, and calls `store.put(key, payload)`. It returns the `key` string so downstream knots can chain metadata-update operations.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `batch` | `Knot` | yes | Parent knot producing a `DataBatch`. |
| `store` | `ObjectStore` | yes | Where to write the bytes. |
| `format` | `FileFormat` | yes | Encodes rows into bytes. |
| `key` | `str` | yes | Destination object key / path. |

**See also:** [Lakehouse Sinks](#lakehouse), [Connectors — Format Matrix](../connectors/index.md)

---

## Transforms

Transform knots accept a `DataBatch` parent and return a new `DataBatch`. They live under `pirn_data.transforms` and all operate on Tier-1 dicts — no extra dependencies required.

| Class | Import | What it does |
|-------|--------|-------------|
| `Filter` | `pirn_data.transforms.filter` | Keeps rows where `predicate(row)` is truthy; drops the rest. |
| `Rename` | `pirn_data.transforms.rename` | Renames columns according to a `dict[str, str]` mapping. |
| `Cast` | `pirn_data.transforms.cast` | Coerces column values to target Python types. |
| `Normalize` | `pirn_data.transforms.normalize` | Applies lightweight string-cleanup rules per column (strip, lower, upper, replace). |
| `Aggregate` | `pirn_data.transforms.aggregate` | Groups by one or more columns and computes per-group aggregations (count, sum, mean, min, max, first, last, count_distinct). |
| `Deduplicate` | `pirn_data.transforms.deduplicate` | Removes duplicate rows, optionally keyed by a subset of columns. |

Example — filter then aggregate:

```python
from pirn_data.transforms.filter import Filter
from pirn_data.transforms.aggregate import Aggregate
from pirn_data.transforms.aggregate_spec import AggregateSpec

active = Filter(
    batch=source,
    predicate=lambda row: row["status"] == "active",
    _config=KnotConfig(id="active_only"),
)

summary = Aggregate(
    batch=active,
    by=["region"],
    aggs={"revenue": AggregateSpec(op="sum", column="revenue")},
    _config=KnotConfig(id="region_revenue"),
)
```

Null handling in `Aggregate`: aggregations skip `None` values. Empty groups after null filtering yield `None` for mean/min/max/first/last and `0` for count/count_distinct.

**See also:** [Specializations](#specializations)

---

## File Formats

Formats live under `pirn.connectors.file_formats`. Each format implements the `FileFormat` interface: `read(body: AsyncIterator[bytes]) -> AsyncIterator[Mapping[str, Any]]` and `write(records: ...) -> AsyncIterator[bytes]`.

### BatchFileFormat vs StreamingFileFormat

There are two base classes:

| Base | `streaming` | How it works | When to use |
|------|-------------|-------------|-------------|
| `BatchFileFormat` | `False` | Buffers the entire payload before decoding; buffers all records before encoding. Subclasses implement `_decode_full(bytes)` and `_encode_full(records)`. | Formats whose libraries require random access or full-file context: XLSX, PDF, HDF5, DICOM, OpenSlide, etc. |
| `StreamingFileFormat` | `True` | Subclasses implement `read` / `write` directly against async iterators. | Formats that can decode incrementally: CSV, JSON Lines, FASTQ, Parquet row-groups, Arrow IPC, etc. |

Both bases provide `_drain_bytes(body)` and `_drain_records(records)` helpers that materialise the async stream into a concrete `bytes` or `list` when needed.

### CompressedFileFormat

Wraps any `FileFormat` with a transparent codec. The resulting format's `name` is `"{inner.name}+{codec}"`.

```python
from pirn.connectors.file_formats.compressed_file_format import CompressedFileFormat
from pirn.connectors.file_formats.parquet_format import ParquetFormat
from pirn.connectors.file_formats.csv_format import CsvFormat

parquet_zst = CompressedFileFormat(ParquetFormat(), codec="zstd")
csv_gz      = CompressedFileFormat(CsvFormat(), codec="gzip")
```

Supported codecs:

| Codec | Extra needed | Notes |
|-------|-------------|-------|
| `"gzip"` | none (stdlib) | Always available. |
| `"bzip2"` | none (stdlib) | Always available. |
| `"zstd"` | `pirn-core[zstd]` | Requires `zstandard`. |
| `"snappy"` | `pirn-core[snappy]` | Requires `python-snappy`. |
| `"lz4"` | `pirn-core[lz4]` | Requires `lz4`. |

### ArchiveFileFormat

Wraps a `FileFormat` for tar/zip multi-file archives. On read, each archive member is decoded and records are tagged with `{"_archive_member": "<member path>", ...}`. On write, each record must carry `_archive_member`.

```python
from pirn.connectors.file_formats.archive_file_format import ArchiveFileFormat
from pirn.connectors.file_formats.csv_format import CsvFormat

archive = ArchiveFileFormat(CsvFormat(), archive_type="tar.gz")
# or: archive_type="zip" | "tar" | "tar.bz2" | "tar.zst"
```

`tar.zst` requires `pirn-core[zstd]`. The `streaming` property is always `False` for `ArchiveFileFormat` because the full archive must be buffered.

### Format Reference Table

All ~98 formats grouped by category. Read (R) and Write (W) indicate supported operations. Formats with no write support are read-only.

#### Universal Tabular

| Format | Class | R | W | Streaming | Extra |
|--------|-------|---|---|-----------|-------|
| CSV | `CsvFormat` | ✓ | ✓ | ✓ | none |
| TSV | `TsvFormat` | ✓ | ✓ | ✓ | none |
| JSON | `JsonFormat` | ✓ | ✓ | ✓ | none |
| JSON Lines | `JsonlFormat` | ✓ | ✓ | ✓ | none |
| Parquet | `ParquetFormat` | ✓ | ✓ | ✓ | `pirn-core[parquet]` (pyarrow) |
| Apache ORC | `OrcFormat` | ✓ | ✓ | — | `pirn-core[orc]` |
| Apache Avro | `AvroFormat` | ✓ | ✓ | — | `pirn-core[avro]` |
| Apache Arrow IPC | `ArrowIpcFormat` | ✓ | ✓ | ✓ | `pirn-core[arrow]` (pyarrow) |
| Apache Feather v2 | `FeatherFormat` | ✓ | ✓ | — | `pirn-core[feather]` |
| XLSX | `XlsxFormat` | ✓ | ✓ | — | `pirn-core[xlsx]` |
| ODS | `OdsFormat` | ✓ | ✓ | — | `pirn-core[ods]` |

#### Scientific / Numerical

| Format | Class | R | W | Streaming | Extra |
|--------|-------|---|---|-----------|-------|
| HDF5 | `Hdf5Format` | ✓ | ✓ | — | `pirn-core[hdf5]` |
| Zarr | `ZarrFormat` | ✓ | ✓ | — | `pirn-core[zarr]` |
| MATLAB .mat | `MatlabMatFormat` | ✓ | ✓ | — | `pirn-core[matlab]` |
| NetCDF (classic) | `NetcdfFormat` | ✓ | ✓ | — | `pirn-core[netcdf]` |
| NetCDF4 | `Netcdf4Format` | ✓ | ✓ | — | `pirn-core[netcdf]` |
| FITS (astronomy) | `FitsFormat` | ✓ | ✓ | — | `pirn-core[fits]` |
| ASDF | `AsdfFormat` | ✓ | ✓ | — | `pirn-core[asdf]` |
| NumPy .npy | `NumpyNpyFormat` | ✓ | ✓ | — | none (base install) |
| NumPy .npz | `NumpyNpzFormat` | ✓ | ✓ | — | none (base install) |
| MzML (mass spec) | `MzmlFormat` | ✓ | ✓ | — | `pirn-core[pyteomics]` / `pirn-core[html]` |
| ROOT (particle physics) | `RootFormat` | ✓ | — | — | `pirn-core[root]` |

#### Documents

| Format | Class | R | W | Streaming | Extra |
|--------|-------|---|---|-----------|-------|
| PDF | `PdfFormat` | ✓ | ✓ | — | `pirn-core[pdf]` |
| DOCX | `DocxFormat` | ✓ | ✓ | — | `pirn-core[docx]` |
| PPTX | `PptxFormat` | ✓ | ✓ | — | `pirn-core[pptx]` |
| HTML | `HtmlFormat` | ✓ | ✓ | — | `pirn-core[html]` |
| Markdown | `MarkdownFormat` | ✓ | ✓ | ✓ | `pirn-core[markdown]` |
| EPUB | `EpubFormat` | ✓ | ✓ | — | `pirn-core[epub]` |
| RTF | `RtfFormat` | ✓ | ✓ | — | `pirn-core[rtf]` |
| Plain text | `PlainTextFormat` | ✓ | ✓ | ✓ | none |

#### Genomics

| Format | Class | R | W | Streaming | Extra |
|--------|-------|---|---|-----------|-------|
| FASTA | `FastaFormat` | ✓ | ✓ | ✓ | none (base install) |
| FASTQ | `FastqFormat` | ✓ | ✓ | ✓ | none (stdlib parse path) |
| VCF | `VcfFormat` | ✓ | ✓ | ✓ | none (base install) |
| BCF | `BcfFormat` | ✓ | ✓ | — | `pirn-health[genomics]` |
| BAM | `BamFormat` | ✓ | ✓ | — | `pirn-health[genomics]` |
| CRAM | `CramFormat` | ✓ | ✓ | — | `pirn-health[genomics]` |
| SAM | `SamFormat` | ✓ | ✓ | ✓ | `pirn-health[genomics]` |

#### Geospatial

| Format | Class | R | W | Streaming | Extra |
|--------|-------|---|---|-----------|-------|
| Shapefile | `ShapefileFormat` | ✓ | ✓ | — | `pirn-core[shapefile]` |
| GeoJSON | `GeoJsonFormat` | ✓ | ✓ | ✓ | none (base install) |
| KML | `KmlFormat` | ✓ | ✓ | — | `pirn-core[kml]` |
| GeoTIFF | `GeotiffFormat` | ✓ | ✓ | — | `pirn-core[geotiff]` |
| GeoPackage | `GeopackageFormat` | ✓ | ✓ | — | `pirn-core[geopackage]` |

#### ML Artifacts

| Format | Class | R | W | Streaming | Extra |
|--------|-------|---|---|-----------|-------|
| ONNX | `OnnxFormat` | ✓ | ✓ | — | `pirn-core[onnx]` |
| SafeTensors | `SafetensorsFormat` | ✓ | ✓ | — | `pirn-core[safetensors]` |
| Joblib | `JoblibFormat` | ✓ | ✓ | — | `pirn-core[joblib]` |
| PyTorch (.pt/.pth) | `PytorchFormat` | ✓ | ✓ | — | `pirn-core[pytorch]` |
| TensorFlow SavedModel | `TfSavedModelFormat` | ✓ | ✓ | — | `pirn-core[tensorflow]` |
| TFLite | `TfliteFormat` | ✓ | ✓ | — | `pirn-core[tflite]` / `pirn-core[tensorflow]` |
| GGUF | `GgufFormat` | ✓ | ✓ | — | `pirn-core[gguf]` |

#### Images

| Format | Class | R | W | Streaming | Extra |
|--------|-------|---|---|-----------|-------|
| PNG | `PngFormat` | ✓ | ✓ | — | `pirn-core[image]` |
| JPEG | `JpegFormat` | ✓ | ✓ | — | `pirn-core[image]` |
| WebP | `WebpFormat` | ✓ | ✓ | — | `pirn-core[image]` |
| HEIC | `HeicFormat` | ✓ | ✓ | — | `pirn-core[heic]` |
| TIFF (multi-page) | `TiffFormat` | ✓ | ✓ | — | `pirn-core[tiff]` |

#### Healthcare — Imaging

| Format | Class | R | W | Streaming | PHI Safety | Extra |
|--------|-------|---|---|-----------|-----------|-------|
| DICOM | `DicomFormat` | ✓ | ✓ | — | PatientID hashed; name/dob/address dropped | `pirn-health[health]` |
| Whole-slide (OpenSlide) | `OpenSlideFormat` | ✓ | — | — | — | `pirn-health[health]` |
| NIfTI | `NiftiFormat` | ✓ | ✓ | — | — | `pirn-health[health]` |

#### Healthcare — Clinical

| Format | Class | R | W | Streaming | PHI Safety | Extra |
|--------|-------|---|---|-----------|-----------|-------|
| HL7 v2 | `Hl7v2Format` | ✓ | ✓ | — | PID.3/5/7/11/18/19/20 redacted | `pirn-core[hl7]` |
| FHIR JSON | `FhirJsonFormat` | ✓ | ✓ | — | PHI fields sanitised | `pirn-health[health]` |
| FHIR XML | `FhirXmlFormat` | ✓ | ✓ | — | PHI fields sanitised | `pirn-health[health]` / `pirn-core[html]` |
| CDA XML | `CdaXmlFormat` | ✓ | ✓ | — | PHI stripped | `pirn-health[health]` / `pirn-core[html]` |
| Define-XML (CDISC) | `DefineXmlFormat` | ✓ | ✓ | — | — | `pirn-health[health]` / `pirn-core[html]` |
| SDTM XPT (SAS transport) | `SdtmXptFormat` | ✓ | ✓ | — | — | `pirn-core[spss]` / `pirn-data[data]` |

#### Healthcare — Biosignal

| Format | Class | R | W | Streaming | Extra |
|--------|-------|---|---|-----------|-------|
| EDF | `EdfFormat` | ✓ | ✓ | — | `pirn-health[health]` |
| EDF+ | `EdfPlusFormat` | ✓ | ✓ | — | none (base install) |
| BDF | `BdfFormat` | ✓ | ✓ | — | `pirn-health[health]` |
| BrainVision | `BrainVisionFormat` | ✓ | ✓ | — | `pirn-health[health]` |
| BIDS dataset | `BidsDatasetFormat` | ✓ | ✓ | — | `pirn-core[bids]` |

#### Audio

| Format | Class | R | W | Streaming | Extra |
|--------|-------|---|---|-----------|-------|
| WAV | `WavFormat` | ✓ | ✓ | — | none (base install) |
| MP3 | `Mp3Format` | ✓ | ✓ | — | `pirn-core[audio]` + ffmpeg |
| AAC | `AacFormat` | ✓ | ✓ | — | `pirn-core[audio]` + ffmpeg |
| OGG | `OggFormat` | ✓ | ✓ | — | `pirn-core[audio]` |
| FLAC | `FlacFormat` | ✓ | ✓ | — | `pirn-core[audio]` |
| M4A | `M4aFormat` | ✓ | ✓ | — | `pirn-core[audio]` + ffmpeg |

#### Oil & Gas

| Format | Class | R | W | Streaming | Extra |
|--------|-------|---|---|-----------|-------|
| SEG-Y | `SegyFormat` | ✓ | ✓ | — | `pirn-oilgas[oilgas]` |
| SEG-D | `SegdFormat` | ✓ | — | — | none (base install) |
| DLIS (well logs) | `DlisFormat` | ✓ | — | — | `pirn-core[dlis]` |
| LAS (well logs) | `LasFormat` | ✓ | ✓ | — | `pirn-oilgas[oilgas]` |
| WITSML | `WitsmlFormat` | ✓ | ✓ | — | `pirn-oilgas[oilgas]` / `pirn-core[html]` |
| PRODML | `ProdmlFormat` | ✓ | ✓ | — | `pirn-oilgas[oilgas]` / `pirn-core[html]` |
| RESQML | `ResqmlFormat` | ✓ | ✓ | — | `pirn-oilgas[oilgas]` / `pirn-core[html]` |

#### Weather / Atmospheric

| Format | Class | R | W | Streaming | Extra |
|--------|-------|---|---|-----------|-------|
| GRIB | `GribFormat` | ✓ | — | — | `pirn-core[grib]` |

#### Compression Codecs

Codecs are not standalone formats; compose them via `CompressedFileFormat`.

| Codec | Class | Extra |
|-------|-------|-------|
| gzip | `GzipCodec` | none (stdlib) |
| bzip2 | `Bzip2Codec` | none (stdlib) |
| zstd | `ZstdCodec` | `pirn-core[zstd]` |
| snappy | `SnappyCodec` | `pirn-core[snappy]` |
| lz4 | `Lz4Codec` | `pirn-core[lz4]` |

#### Archives

| Archive type | Wrapper | Nested format | Extra for tar.zst |
|-------------|---------|--------------|-------------------|
| `tar` | `ArchiveFileFormat(..., archive_type="tar")` | any `FileFormat` | — |
| `tar.gz` | `ArchiveFileFormat(..., archive_type="tar.gz")` | any `FileFormat` | — |
| `tar.bz2` | `ArchiveFileFormat(..., archive_type="tar.bz2")` | any `FileFormat` | — |
| `tar.zst` | `ArchiveFileFormat(..., archive_type="tar.zst")` | any `FileFormat` | `pirn-core[zstd]` |
| `zip` | `ArchiveFileFormat(..., archive_type="zip")` | any `FileFormat` | — |

#### Lakehouse Table Formats

| Format | Class | R | W | Merge | Time-travel | Extra |
|--------|-------|---|---|-------|-------------|-------|
| Delta Lake | `DeltaTable` | ✓ | ✓ | ✓ | ✓ (snapshot_id / as_of_timestamp) | `pirn-data[delta]` |
| Apache Iceberg | `IcebergTable` | ✓ | ✓ | — | ✓ (snapshot_id / as_of_timestamp) | `pirn-data[iceberg]` |
| Apache Hudi | `HudiTable` | ✓ | — | — | ✓ (read path only) | `pirn-data[hudi]` (no-op; reads via pyarrow) |

**See also:** [Lakehouse](#lakehouse)

---

## Lakehouse

The lakehouse adapters live under `pirn_data.lakehouse` and implement the `LakehouseTable` interface. All three adapters are injectable with a pre-built vendor table for testing, and load their vendor SDKs lazily.

### DeltaTable

Full CRUD support backed by the Rust-compiled `deltalake` binding.

```python
from pirn_data.lakehouse.delta.delta_table import DeltaTable
from pirn_data.lakehouse.delta.delta_table_config import DeltaTableConfig
from pirn_data.lakehouse.lakehouse_table_source import LakehouseTableSource

config = DeltaTableConfig(
    table_uri="s3://my-bucket/tables/events",
    storage_options={"AWS_REGION": "us-east-1"},
)
table = DeltaTable(config)

source = LakehouseTableSource(
    table=table,
    filter={"region": "us-east-1"},    # optional partition filter
    columns=["id", "event", "ts"],     # optional column projection
    snapshot_id=5,                     # optional time-travel
    _config=KnotConfig(id="read_events"),
)
```

Supported operations: `scan`, `append`, `overwrite` (full or partition-predicate), `merge` (upsert on key columns), `history`.

### IcebergTable

Read + write backed by `pyiceberg`. Merge is not yet implemented natively in `pyiceberg`'s Python writer as of mid-2026 — `IcebergTable.merge()` raises `NotImplementedError` with a pointer to the upstream issue. Use the Java/Scala writer for production merges.

```python
from pirn_data.lakehouse.iceberg.iceberg_table import IcebergTable
from pirn_data.lakehouse.iceberg.iceberg_table_config import IcebergTableConfig

config = IcebergTableConfig(
    catalog_name="glue",
    table_identifier="my_db.events",
)
table = IcebergTable(config)
```

Supported operations: `scan`, `append`, `overwrite`, `history`. `merge` raises `NotImplementedError`.

### HudiTable

Read-only. The Python ecosystem for Hudi is limited as of mid-2026: stable writes require the Spark/Java writer (`hudi-spark-bundle`). The adapter reads the latest commit's Parquet files directly via `pyarrow`. All write methods raise `NotImplementedError` with a pointer to the Spark writer.

```python
from pirn_data.lakehouse.hudi.hudi_table import HudiTable
from pirn_data.lakehouse.hudi.hudi_table_config import HudiTableConfig

config = HudiTableConfig(
    table_path="s3://my-bucket/tables/events",
    table_type="COPY_ON_WRITE",   # or "MERGE_ON_READ"
)
table = HudiTable(config)
```

`pirn-data[hudi]` is currently a no-op marker extra (no vendor SDK on PyPI under a stable name). The read path depends only on `pyarrow`, which ships with `pirn-data[data]`.

**See also:** [Connectors — Format Matrix](../connectors/index.md)

---

## Specializations

The `pirn_data.specializations` package bundles higher-level knot compositions for common patterns. No new concepts are introduced — these are pre-wired combinations of sources, transforms, sinks, and lakehouse adapters.

### Ingestion patterns (`ingestion/`)

| Class | What it does |
|-------|-------------|
| `AppendOnlyIngest` | Reads a source and appends to a lakehouse table. |
| `FullRefreshExtract` | Truncates a target table then reloads from source. |
| `WatermarkIncrementalExtract` | Reads only rows newer than a high-water-mark timestamp. |
| `ReadHighWaterMarkKnot` | Reads the current high-water mark from a metadata store. |
| `QueryNewRowsKnot` | Fetches rows with `created_at > watermark`. |
| `TruncateTableKnot` | Issues a truncate against the target. |
| `GateRowsBehindTruncateKnot` | Ensures truncation completes before writes begin. |

### Medallion patterns (`medallion/`)

| Class | What it does |
|-------|-------------|
| `BronzeRawIngest` | Lands raw bytes verbatim to the Bronze layer with audit metadata. |
| `SilverCleanTransform` | Applies type casting, normalisation, and deduplication for the Silver layer. |
| `GoldAggregation` | Produces business aggregates for the Gold layer. |
| `StampBronzeMetadataKnot` | Attaches ingest timestamp, source URI, and schema version. |
| `DataBatchToTuplesKnot` / `TuplesToDataBatchKnot` | Converts between `DataBatch` and `tuple[dict]` for low-overhead inter-knot handoff. |

### SCD / CDC patterns (`scd/`)

| Class | What it does |
|-------|-------------|
| `ScdType1` | Overwrite the current record on change (no history). |
| `ScdType2` | Maintain row history with `valid_from` / `valid_to` / `is_current`; set `row_hash_column` for dbt-snapshot hash change detection. |
| `ScdType3PreviousValue` | Keep the one prior value in a `previous_*` column. |
| `ScdType4MiniDimension` | Split fast-changing attributes into a mini-dimension. |
| `ScdType5MiniDimWithCurrent` | Mini-dimension plus a current-value outrigger on the base dimension. |
| `ScdType6Hybrid` | Type 2 history with `current_*` and `previous_*` columns on every row. |
| `ScdType7` | Surrogate-keyed Type 2 history; `current_columns` adds the Type 1 current view. |
| `CDCDebezium` | Applies Debezium CDC event envelopes (op=c/u/d) to a target table. |
| `DebeziumSource` | Reads Debezium-formatted CDC events from a topic. |

**See also:** [Transforms](#transforms), [Lakehouse](#lakehouse), [Architecture — Tiered Data Domain](../architecture/overview.md)
