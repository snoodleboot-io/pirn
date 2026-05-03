# Phase 3 Review — 2026-05-01

Multi-axis audit of the Phase 3 work (commits `1c64d10..fbd44ed` on
`feat/domain-knot-libraries`). Four parallel read-only review agents
covered conventions, standards, security, and performance.

**Headline:** 29 BLOCKING + 24 MEDIUM + 15 LOW = 68 findings.

The BLOCKING items are conventions violations introduced by parallel
agents during the Phase 3 sprint. They are mechanical to fix —
multi-class files need splitting, module-level helpers need wrapping
into the relevant classes. Same bar as Batch 1 / Batch 2 cleanup.

Two SECURITY findings (`B5-1`, `B5-2`) are MEDIUM by severity but
should be treated as BLOCKING because they introduce real attack
surface (path traversal + SSRF on a publicly-callable knot).

The HIGH PERFORMANCE findings are real but most are gated by stub
status — SCD N+1 patterns matter when SCD is plumbed against real
backends, not while the knots are stubs.

---

## Conventions audit (24 BLOCKING / 4 MEDIUM / 2 LOW)

### BLOCKING — 10 module-level free functions in agent specializations

These were extracted as private helpers (`_extract_text`, `_load_text`)
but left at module scope. Convention says methods belong to classes
(decorators + thin public-API wrappers exempt). All in
`pirn/domains/agents/specializations/`:

- `rag/relevance_gate.py:19` — `_default_scorer`
- `specialized_agents/{code,sql,data_analyst}_agent.py` — `_extract_text` (3 sites)
- `document_processing/document_translation_pipeline.py:58,112` — `_load_text`, `_extract_text`
- `document_processing/document_summarizer_pipeline.py:65,151` — same pair
- `document_processing/document_qa_pipeline.py:59,162` — same pair

**Fix:** move each into the relevant Knot as a `@staticmethod`.

### BLOCKING — 14 multi-class files

The convention is one class per file. Phase 3 introduced helper Knots
co-located with their parent SubTapestry. Same rule as the SparkCompute
split in Batch 1 (`SparkWriteSink` + `SparkCollectSink`).

`pirn/domains/agents/specializations/`:
- `specialized_agents/code_agent.py` — 4 classes
- `specialized_agents/sql_agent.py` — 4 classes
- `specialized_agents/data_analyst_agent.py` — 2 classes
- `document_processing/document_ingestion_pipeline.py` — 4 classes
- `document_processing/document_qa_pipeline.py` — 3 classes
- `document_processing/document_summarizer_pipeline.py` — 3 classes
- `document_processing/document_translation_pipeline.py` — 3 classes
- `structured_output/json_extractor_pipeline.py` — 2 classes
- `structured_output/yaml_extractor_pipeline.py` — 2 classes
- `structured_output/enum_classifier_pipeline.py` — 2 classes

`pirn/domains/health/`:
- `clinical/clinical_data_quality_gate.py` — exception + gate
- `clinical/medication_reconciliation_pipeline.py` — 2 classes
- `clinical/patient_cohort_builder.py` — 2 classes
- `genomics/genomics_qc_gate.py` — exception + gate

**Fix:** split each helper class into its own snake_case file.

### MEDIUM — 4 file-naming inconsistencies

SCD specializations mix two casing styles:
- `scd_type_1.py` → `ScdType1`
- `scd_type_1_overwrite.py` → `SCDType1Overwrite` (and `_history`, `_hybrid` variants)

**Fix:** standardise on `ScdType*` (PascalCase "Scd" is more PEP-8-friendly).
Rename `SCDType1Overwrite` → `ScdType1Overwrite`, etc.

### LOW — 2 pre-existing free functions

`pirn/core/hashing.py:36,63` — `content_hash` and `_canonicalise` at
module level. Pre-existing pattern; Phase 3 only modified bodies.
Punt to a follow-up `ContentHasher` class refactor.

---

## Standards audit (0 BLOCKING / 9 MEDIUM / 4 LOW)

### MEDIUM — 6 SubTapestries return `RunResult` instead of typed/summary

Convention says SubTapestry returns a primitive summary OR a single
typed value (cf. `ScdType1.process` returning `dict[str, Any]`,
`NaiveRAGPipeline.process` extracting a typed `AgentResponse`).
These don't:

- `health/clinical/medication_reconciliation_pipeline.py:76`
- `health/clinical/patient_cohort_builder.py:102`
- `oilgas/workflows/wellbore_petrophysics_workflow.py:122`
- `oilgas/workflows/decline_curve_reserves_workflow.py:97`
- `oilgas/workflows/seismic_to_well_tie_workflow.py:96`
- `oilgas/workflows/field_production_reporting_workflow.py:134`

**Fix:** extract a typed leaf output (e.g.,
`inner_result.outputs["evaluate"]`) or return a primitive summary dict.

### MEDIUM — 3 SCD classes wrongly inherit from `SubTapestry`

`SCDType1Overwrite`, `SCDType2History`, `SCDType7Hybrid` all extend
`SubTapestry` but their `process()` does NOT compose an inner Tapestry
— they execute SQL inline. Should be `Knot` subclasses, matching their
`*MergeKnot` siblings.

**Fix:** change `class X(SubTapestry):` → `class X(Knot):` and remove
the inner-Tapestry scaffolding.

### MEDIUM — `PatientCohortBuilder` has no actual pipeline edges

`health/clinical/patient_cohort_builder.py:84-101` constructs filters
inside an inner Tapestry but doesn't wire `records=previous_filter`
between stages. The Python-side prefiltering at construction time is
what actually does the work; the engine never executes the filters
because there are no edges. The pipeline IS the construction loop.

**Fix:** wire `records=previous_stage_knot` so each filter consumes
the previous filter's output via the engine, not Python-side.

### LOW — Misc style

- `regression_pipeline.py:28` — `_regression_metrics: tuple` should be
  `ClassVar[tuple]`.
- `cdc_debezium.py` lives at scd/ root while `cdc/debezium_source.py`
  lives under cdc/ — pick one location.
- Several health stub knots store config without forwarding through
  `super().__init__()` (loses config visibility in
  `Knot.config_values`).

---

## Security audit (0 BLOCKING / 3 MEDIUM / 4 LOW)

### MEDIUM — `B5-1` Path traversal in `_DocumentLoader`

`pirn/domains/agents/specializations/document_processing/document_ingestion_pipeline.py:40-49`
accepts an arbitrary `source` string. URLs without an `http(s)` scheme
fall through to `_read_file(source)` which calls `Path(source).read_text(...)`.
**No path-traversal guard, no allowlist, no symlink check, no max-size
limit.** An attacker who can influence `source` reads
`/etc/passwd`, `/root/.aws/credentials`, etc. `file://`-scheme URLs
fall into the same branch.

**Fix (treat as BLOCKING):** require `Path(source).resolve()` to live
under a caller-supplied `allowed_root`; reject symlinks; cap file
size.

### MEDIUM — `B5-2` SSRF in `_DocumentLoader._fetch_url`

Same file, lines 55-67. No host allowlist, no rejection of RFC1918 /
link-local / loopback. Attackers can fetch:
- AWS IMDS: `http://169.254.169.254/latest/meta-data/`
- Consul: `http://127.0.0.1:8500/...`
- Local Redis: `http://localhost:6379/...`

**Fix (treat as BLOCKING):** resolve hostname; reject if
`ipaddress.ip_address(...).is_private | is_loopback | is_link_local | is_reserved`.

### MEDIUM — `B2-1` Health types emit raw PHI in audit dicts

`_pirn_audit_dict()` on `ClinicalRecord`, `RawEEG`, `ClinicalTrialRecord`,
`GenomicsRecord` returns `patient_id`, `subject_id`, `sample_id`,
`trial_id`, `encounter_id` in the clear. Audit emission is supposed
to be a sanctioned channel — but unhashed direct identifiers in HIPAA
contexts is a violation.

**Fix:** route every direct identifier through a tokenizer (the
existing `PHIRedactor._hash_id` pattern). Either return
`f"hash:{sha256(salt|value)[:16]}"` or document that audit emission
is post-tokenisation only and add a per-process audit salt.

### LOW — `B3-1` Missing `_clear_credentials` on 6 protocol bases

`MemoryStore`, `LLMProvider`, `Tool`, `FHIRClient`, `PACSClient`,
`OMOPConnection` lack the `_clear_credentials(self) -> None: self._config = None`
helper that the ML providers got. Concrete subclasses re-invent it.

**Fix:** add to all six.

### LOW — Other

- `B4-1` `_DocumentLoader._fetch_url` constructs `httpx.AsyncClient`
  without `timeout=` (slow-loris risk).
- `B5-3` File-path validation on genomics/oilgas stubs needs hardening
  before flipping to real I/O.
- `B6-1` `zenpy` has slow security-patch cadence — track via SBOM.

---

## Performance audit (5 HIGH / 8 MEDIUM / 5 LOW)

### HIGH — SCD knots N+1 query patterns

`scd_type_1_overwrite.py:110-125`, `scd_type_2_history.py:152-179`,
`scd_type_7_hybrid.py:185-225` issue per-row queries inside a loop.
For N source rows: 2N–5N database roundtrips.

**Fix:** bulk-select existing keys once, partition source into
inserts/updates locally, then one `execute_many` per category. The
sibling `*MergeKnot` classes already show the correct pattern.

### HIGH — CDC Debezium materialises full stream

`scd/cdc/debezium_source.py:95-99` consumes the entire async stream
into `events: list[Mapping]` before returning. CDC topics are
unbounded — this defeats streaming.

**Fix:** return `AsyncIterator` directly OR refuse to call `process()`
without `max_messages` set.

### HIGH — `_canonicalise` constructs `TypeAdapter` per call

`pirn/core/hashing.py:114` allocates a fresh `TypeAdapter(type(value))`
per call. Pydantic caches internals but the constructor still walks
the type and builds schema/validator pairs (~10-100 µs each). At
millions of canonicalisations per tapestry, the cost compounds.

**Fix:** module-level `_TYPE_ADAPTER_CACHE: dict[type, TypeAdapter]`.

### HIGH — `DocumentSummarizerPipeline` sequential LLM calls

`document_summarizer_pipeline.py:96-103` runs map-reduce summarisation
sequentially: `for chunk in chunks: partial_summaries.append(await
self._summarise_chunk(...))`. For a 50-chunk doc with 1.5s/LLM-call:
~75s sequential vs ~2-3s with `asyncio.gather`.

**Fix:** `partial_summaries = await asyncio.gather(*(self._summarise_chunk(...) for chunk in chunks))`.
The pattern from `parallel_specialist_fan_out.py:69` is the model.

### HIGH — `_canonicalise` `hasattr` ordering

`pirn/core/hashing.py:91` checks `hasattr(value, "__pirn_canonical__")`
BEFORE the primitive check. `hasattr` allocates an exception on miss.
For simple values (int, str, dict — the common case) this fires every
call.

**Fix:** put the primitive isinstance guard FIRST, then bytes / Mapping
/ Sequence, then `__pirn_canonical__` last.

### MEDIUM — Sync I/O in async contexts

`document_summarizer_pipeline.py:79`, `document_qa_pipeline.py`,
`document_translation_pipeline.py`, `document_ingestion_pipeline.py`:
`Path(source).read_text(encoding="utf-8")` inside `async def`. Blocks
the event loop on multi-MB documents.

`ml/data_prep/dataset_loader.py:112` — `pq.read_table(self._parquet_path)`
inside `async def _count_parquet_rows`.

**Fix:** wrap with `await asyncio.to_thread(...)`.

### MEDIUM — SCD properties recompute SQL per row

`scd_type_1_overwrite.py:115,119,123` reference `self.select_existing_query`,
`self.update_query`, `self.insert_query` inside a per-row loop. Each
property runs `" AND ".join(...)` / `" , ".join(...)` to rebuild the
same SQL. For N rows: 3N redundant string builds.

**Fix:** cache in `__init__` or use `@functools.cached_property`.
Same applies to `scd_type_2_history.py:159,164,173,177` and
`scd_type_7_hybrid.py:192,197,209,213,224`.

### MEDIUM — Sequential vector-store writes

`document_ingestion_pipeline.py:154-164` per-chunk `await self._store.store(...)`
in a loop. For 1k-chunk documents into a remote vector DB: minutes vs
seconds.

**Fix:** `asyncio.gather` (or expose `MemoryStore.store_many`).

### LOW — Misc

- `code_agent.py:85` `import ast` inside `process()`; hoist to module
  top.
- `hashing.py:112` `from pydantic import TypeAdapter` inside the
  function; hoist.
- `hashing.py:125` `sorted(value.keys(), key=str)` redundant when keys
  are already strings.

---

## Fix plan

### Wave 1 — BLOCKING (must merge fix)

Conventions cleanup. ~17 file splits + 10 free-function wraps + 4
file renames. Mechanical; agents can do it in parallel:
- 1 agent for `pirn/domains/agents/specializations/` splits + free-func wraps
- 1 agent for `pirn/domains/health/` splits
- 1 agent for SCD class-name standardisation

### Wave 2 — Security MEDIUM (treat as BLOCKING)

`_DocumentLoader` path traversal + SSRF. 4-file scope. Direct fix.

### Wave 3 — Performance HIGH

- TypeAdapter cache + hashing reorder + module-level imports (1 file).
- SCD N+1 → bulk pattern (3 files; affects real-backend perf only).
- DocumentSummarizerPipeline + DocumentIngestionPipeline → asyncio.gather.

### Wave 4 — Standards MEDIUM (deferred)

- 6 SubTapestry typed-return refactors.
- 3 SCD inline classes Knot vs SubTapestry corrections.
- PatientCohortBuilder pipeline-edge fix.
- These are correctness-of-design issues; tests still pass because the
  current shapes happen to work. Can land in a follow-up PR.

### Wave 5 — LOW

- B3-1 `_clear_credentials` on 6 protocol bases.
- httpx timeout in `_DocumentLoader`.
- File-path validation hardening on stub knots.
- Misc style cleanups.

Wave 5 can land in the same follow-up PR as Wave 4.
