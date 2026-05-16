# Delivery Stories

---

## Story 1: Domain Implementation — Hollow Knot Remediation

**As a** pirn user working in a domain (health, signal, oilgas, ml, agents, data)
**I want** domain knots with real algorithmic implementations
**So that** I can compose production pipelines without writing domain logic from scratch

### Acceptance Criteria
- Every non-interface, non-type `process()` calls a real computation library or external SDK
- No knot validates inputs and returns a correctly-typed struct without computing anything

### Features
- **Signal domain (~85 files):** All filters (IIR/FIR/adaptive/nonlinear), spectral (FFT/STFT/wavelet), audio (librosa), beamforming — real scipy/numpy/librosa/pywt/padasip calls
- **Health domain (~129 files):** EEG/MEG (MNE), MRI (nibabel/nilearn), genomics, clinical/EHR, wearables, pathology, clinical trials — real scipy/sklearn/MNE computation; 1 intentional gap (OMOP CDM mapper, blocked on vocab DB)
- **OilGas domain (~109 files):** Seismic (segyio), well/petrophysics (lasio), reservoir, production ops, facilities integrity, geospatial — Eclipse/CMG parsers via resfo + stdlib
- **ML domain (~147 files):** Data prep, feature engineering, training, evaluation (SHAP, fairness audit), deployment (shadow deployer, Predictor) — real sklearn/xgboost/shap calls; 4 intentional abstract interfaces remain
- **Agents domain (~175 files):** LLM calls, memory, tool routing, ReAct, RAG, multi-agent, guardrails, structured output — all non-interface files call real LLM/store SDKs
- **Data domain (~100 files):** Tiered architecture implemented — dict/Polars/Pandas/DuckDB/DataFusion/Ibis/Spark/streaming/lakehouse/validation

**Delivered:** 2026-05-10 (signal 2026-05-08, health/oilgas 2026-05-09, ml 2026-05-10)

---

## Story 2: Assembler / Disassembler Refactor

**As a** domain knot author
**I want** assembler and disassembler knots to bridge connector I/O and domain Payloads
**So that** `process()` is always testable in-process and connector knots are reusable across domains

### Acceptance Criteria
- All ingestor knots deleted — none remain in any domain
- Every domain has `assemblers/` and `disassemblers/` directories
- `Assembler` and `Disassembler` base classes exist in `pirn.core`
- No assembler or disassembler performs I/O in `process()`

### Features
- `pirn/core/assembler.py` and `pirn/core/disassembler.py` base classes
- Assembler/disassembler directories in all 7 domains
- Ingestors deleted across all domains (including `audio_file_ingestor.py` and all variants)
- Payload pattern audit passing for agents, data, and connectors

**Delivered:** 2026-05-15 (Phases 1–5 complete)

---

## Story 3: SubTapestry Contract Reform

**As a** pirn user composing nested pipelines
**I want** SubTapestry subclasses to conform to a single correct contract
**So that** inner pipeline failure propagates correctly and runs are safe for concurrent execution

### Acceptance Criteria
- All ~90 domain SubTapestry specializations call `_run_inner()` and return a value derived from it
- No subclass stores a pre-built inner tapestry at construction time
- Inner `SubTapestryError` propagates to outer `Err` without subclass boilerplate

### Features
- Remediation of ~90 SubTapestry subclasses across all domains
- `_run_inner()` return value returned from `process()` in all conforming subclasses
- Run persistence uses materialized path (`run_path` field) for arbitrary-depth nesting
- `children_of(run_id)` method on `RunHistory` for querying nested runs

**Delivered:** 2026-05-10

---

## Story 4: LoopSubTapestry — Iterative Agentic Loops

**As an** agent pipeline author
**I want** a LoopSubTapestry knot that iterates an inner tapestry until a termination condition
**So that** I can build multi-turn agentic loops as a composable pirn node

### Acceptance Criteria
- `LoopSubTapestry` conforms to the SubTapestry contract (Part V design review)
- Iteration terminates on done signal or max-iterations guard
- Each inner run carries its iteration index in run metadata
- CLAUDE.md agentic-loops guide published to `docs/contributing/`

### Features
- `LoopSubTapestry` refactored to SubTapestry contract (commit `56aff20`)
- Agentic-loops contributing guide (`docs/contributing/agentic-loops.md`)
- Part V design review resolved (commit `7612308`)

**Delivered:** 2026-05-15

---

## Story 5: Input Schema Validation (Part III)

**As a** knot author
**I want** input schema assumptions to be explicit and validated
**So that** type mismatches at knot boundaries surface as clear errors rather than silent wrong results

### Acceptance Criteria
- 31 files identified with implicit input schema assumptions are fixed
- Payload pattern audit passes for agents, data, and connectors
- No metadata-only type crosses a pipeline boundary without its data buffer

### Features
- 31 domain files audited and fixed for input schema assumptions
- Payload pattern audit completed for agents, data, and connectors
- Naming sweep completed — ruff N-rules, exception naming, camelCase identifiers, math noqa annotations

**Delivered:** 2026-05-15

---

## Story 6: Documentation Overhaul

**As a** contributor to pirn
**I want** authoritative contributing guides for the key architectural patterns
**So that** new implementations are consistent without requiring design review for every file

### Acceptance Criteria
- Assembler/disassembler pattern documented with contract, naming conventions, folder layout, and test requirements
- Agentic loops guide documents LoopSubTapestry usage and termination patterns

### Features
- `docs/contributing/assembler-disassembler-pattern.md` — complete contributor guide with anti-pattern, contracts, naming, folder layout, reference implementations, and test requirements
- `docs/contributing/agentic-loops.md` — LoopSubTapestry design and usage guide
- Knot remediation rules codified in `docs/contributing/` (gate vs check naming, SubTapestry contract, Payload pattern)

**Delivered:** 2026-05-15
