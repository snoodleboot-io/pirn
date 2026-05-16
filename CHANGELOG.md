# Changelog

All notable changes to pirn are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

#### `@tool` decorator and scalar auto-coercion

- `pirn/domains/agents/tool_decorator.py` — `@tool` decorator converts any sync or async function into a `FunctionTool` (a `Tool` subclass). Name is taken from the function name, description from the first docstring paragraph, and `parameters_schema` from type annotations. Both `Optional[T]` and `list[T]` annotations are handled. Import via `from pirn.domains.agents import tool, FunctionTool`.
- `pirn/core/knot.py` — Framework-level scalar auto-coercion: constructor parameters typed `Knot | T` (or `Union[Knot, T]`) now automatically wrap plain scalars in a `Parameter` node at construction time. The auto-created `Parameter` self-registers in the active `Tapestry` and participates in lineage tracking. Pydantic adapters for those parameters are built against `T` (not `Knot | T`) so validation works correctly at runtime.

#### LoopSubTapestry — iterative, feedback-driven sub-pipelines

`pirn/nodes/loop_sub_tapestry.py` — `LoopSubTapestry[S]` is a `SubTapestry` variant for pipelines where the number of steps is not known ahead of time: LLM agent loops, convergence-driven training, conversational turns. Implement two methods:

- `step(state: S) -> tuple[Tapestry, S] | None` — plan the next iteration or terminate.
- `fold(state: S, result: RunResult) -> S` — integrate an iteration's result into state.

Each iteration is registered as a real `_IterationChainKnot` in the inner tapestry's extensible run, making every step visible in run history and the explorer's drill-down. Zero-iteration loops (where `step` returns `None` immediately) are handled without exception. See `docs/guides/agentic-loops.md`.

#### Assembler / Disassembler pattern — Phases 1–5

Codifies and implements the bridge between pirn's connector layer (raw bytes / rows) and domain knots (typed `Payload` subclasses).

**Core:**
- `pirn/core/assembler.py` — thin `Assembler(Knot)` marker base class.
- `pirn/core/disassembler.py` — thin `Disassembler(Knot)` marker base class.
- `docs/contributing/assembler-disassembler-pattern.md` — convention reference.

**Signal domain:** `SignalObjectStoreAssembler`; `Signal/Spectrum/WaveletObjectStoreDisassembler`.  
**Oil & Gas domain:** `Las/Segy/ScadaDatabase/MudLog/WellCompletionObjectStoreAssembler`; `Las/SegyObjectStoreDisassembler`.  
**Health domain:** `Eeg/Meg/DicomPacs/WsiObjectStore/FhirPatientAssembler`; `Eeg/Meg/Dicom/WsiObjectStoreDisassembler`.  
**ML domain:** `TrainedModelObjectStoreAssembler`; `TrainedModel/Dataset/DataSplit ObjectStoreDisassembler`, `EvalReportDatabaseDisassembler`.

Eleven ingestor knots deleted (they collapsed I/O and assembly into one step, making them untestable and non-reusable): `AudioFileIngestor`, `LasFileIngester`, `SegyFileIngester`, `ScadaHistorianIngester`, `MudLoggingIngester`, `WellCompletionIngester`, `EEGRawIngestor`, `MegRawIngestor`, `DICOMIngestor`, `WsiTileExtractor`, `FhirPatientIngestor`.

#### Optional-dependency skip guards — 159 test files

All 159 unit test files that exercise optional-dependency code now wrap imports in `try/except ImportError as _e: raise unittest.SkipTest(...)` guards. Tests run against a minimal install (no optional deps) without collection errors; they run fully when deps are installed.

#### lance 1.x API migration

`pirn/domains/data/specialized/lance/` updated to the lance 1.x API:
- `arrow_to_lance_sink.py`: `from lance.dataset import write_dataset` (replaces `lance.write_dataset`).
- `lance_source.py`: `from lance.dataset import LanceDataset as _LanceDataset` (replaces `lance.dataset(path)` callable).
- `pyproject.toml`: `lance` optional extra corrected from `pylance>=0.18` (VS Code extension) to `lance>=1.0` (LanceDB library).

### Changed

#### Agent control knots renamed

The four knots in `pirn/domains/agents/control/` were renamed to remove the misleading `Gate` suffix — `Gate` in pirn is a specific framework primitive (predicate pass-through → `Ok` or `Skipped`) and these knots do not extend it:

| Old name | New name |
|----------|----------|
| `SafetyGate` | `SafetyCheck` |
| `TerminationGate` | `TerminationCheck` |
| `ReflectionGate` | `ReflectionCheck` |
| `HandoffGate` | `HandoffCheck` |

Module paths updated accordingly (`safety_gate.py` → `safety_check.py`, etc.). The `ReActLoop`-internal `ReactTerminationGate` is similarly renamed to `ReactTerminationCheck`.

#### SubTapestry contract — `process()` returns `Knot`, not `RunResult`

`SubTapestry.process()` now returns the terminal `Knot` of the inner graph. The base class owns the `Tapestry()` context and calls `_run_inner` — subclasses must not open a `Tapestry()` context or call `_run_inner` directly. All existing SubTapestry subclasses (~90) have been migrated. The old contract raised `SubTapestryError` on inner failure; the new contract surfaces `Err` through the standard result chain.

Two new hooks on `SubTapestry` support specialised subclasses:
- `_extensible_inner_run: ClassVar[bool]` — when `True`, skips sink-registration validation and runs the inner tapestry in extensible mode.
- `_resolve_output_key(sink) -> str` — override to select which inner knot's output is surfaced as this SubTapestry's result.

---

### Added (prior)

#### Agentic design patterns guide

`pirn/domains/agents/PATTERNS.md` — a comprehensive reference covering 18 agentic and multi-agentic design patterns with real knot wiring examples: single agent, ReAct loop, planner/router/executor, generator+critic, coordinator/dispatcher, parallel fan-out/gather, synthesiser, hierarchical decomposition, blackboard (MAS shared state), supervision (guardrail stacking), debate framework, four memory patterns, four RAG variants, structured output extraction, specialised agents, agent-as-tool, MCP usage, and swarm (decentralised multi-agent). Every entry maps to the concrete `pirn.domains.agents` knot that implements it.

#### New examples

Seven domain-format examples added to `examples/domain_formats/`:

- **`medical_triage_agent.py`** — Dynamic DAG over a synthetic DICOM study queue; windowing, tissue classification, and anomaly detection knots run concurrently per study; triage decisions route the next study or terminate. Record schema matches `DicomFormat.decode()`.
- **`seismic_survey_pipeline.py`** — SEG-Y trace QC and attribute extraction pipeline; parallel frequency analysis and amplitude QC converge into survey reports. Schema matches `SegyFormat`.
- **`weather_forecast_pipeline.py`** — Synthetic GRIB ensemble pipeline; surface parameter extraction, alert checking, and forecast report assembly. Schema matches `GribFormat`.
- **`ml_evaluation_loop.py`** — Dynamic evaluation loop that registers a benchmark suite (accuracy, latency, memory) per model candidate and promotes or rejects each.
- **`geospatial_layer_analysis.py`** — Site suitability scoring over synthetic GeoJSON/Shapefile layers; four spatial analysis knots run in parallel per site.
- **`hl7v2_message_router.py`** — HL7 v2 message routing pipeline; type-specific handler knots with PHI scrubbing aligned to `Hl7v2Format`.
- **`genomics_batch_qc.py`** — FASTQ sequencing run QC; quality trimming, alignment simulation, and metric assembly. Schema matches `FastqFormat`.

`examples/llm_agent/agent_loop_v2.py` — Rewritten to use real `pirn.domains.agents` composites. The dynamic DAG shell is identical to `agent_loop.py`; action knots now use `ContextBuilder → LLMCall → OutputParser` (`llm_task`), `ReActLoop` (`react`), and `ContextBuilder → Planner → ToolRouter → ToolExecutor` (`planner`). `StubLLMProvider` and `StubTool` satisfy the interfaces without network access.

### Fixed

#### SQLiteHistory bytes and datetime serialization

`SQLiteHistory.record_run()` previously called `model.model_dump_json()` directly, which hard-fails on pydantic models containing `bytes` fields (encoding error) or bare `datetime` objects (not JSON-serialisable). Replaced with `_model_to_json(model)` — a thin wrapper over `json.dumps(model.model_dump(mode="python"), default=_json_default)` where `_json_default` encodes `bytes` as `{"__bytes_b64__": "<base64>"}`, `datetime`/`date` objects via `.isoformat()`, and dataclasses via `dataclasses.asdict()`. All example pipelines including those with binary-payload formats (DICOM, SEG-Y, GRIB) now persist run history correctly without per-pipeline workarounds.

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
