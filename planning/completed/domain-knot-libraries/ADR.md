# ADR: Domain Knot Libraries — Architectural Decisions

**Status:** Accepted
**Date:** 2026-05-15
**Branch:** feat/domain-gap-remediation-plan

---

## ADR-1: Payload[M, D] Generic Base

### Context

Domain knots need to carry two things through the pirn transport layer:

1. **Metadata** — a typed descriptor providing provenance, lineage, and structural context (e.g. `SignalFrame`, `LASFile`, `DICOMSeries`). Generic code and the audit trail operate against this.
2. **Data** — the actual computation result (numpy arrays, fitted models, metric dicts, waveforms). Domain knots operate against this.

Before this decision, some knots passed metadata-only types through the pipeline, or collapsed metadata and data into an untyped dict. Downstream knots could not distinguish "I have the data" from "I have a description of the data." The assembler/disassembler pattern required a single typed base that any assembler could return and any domain knot could accept. Without a common base, type annotations at the connector–domain boundary were `Any`.

### Decision

Introduce `Payload[M, D]` in `pirn/core/payload.py` as the generic base class for all domain payload types.

```python
class Payload(PirnOpaqueValue, Generic[M, D]):
    def __init__(self, metadata: M, data: D) -> None: ...
    @property
    def metadata(self) -> M: ...
    @property
    def data(self) -> D: ...
    def _pirn_audit_dict(self) -> dict[str, Any]: ...
```

Concrete subclasses expose domain-readable aliases as read-only properties backed by `_metadata` / `_data`. Examples:
- `SignalPayload(Payload[SignalFrame, np.ndarray])` — exposes `.frame` and `.samples`
- `TrainedModelPayload(Payload[ModelMetadata, Any])` — exposes `.model_metadata` and `.estimator`

Generic transport and serialisation code programs against `.metadata` / `.data`. Domain knots use the semantic property names. Serialisation delegates to `PickleSerializer` fallback in `SerializerRegistry`. The audit dict delegates entirely to `metadata._pirn_audit_dict()`.

`Payload` extends `PirnOpaqueValue`, signalling to the framework that the type is opaque and not introspected for field extraction.

### Alternatives Rejected

| Alternative | Reason Rejected |
|-------------|----------------|
| Typed dataclasses per domain, no shared base | No common type for assembler return annotations; type checker cannot verify assembler output is framework-handled. |
| Single `Payload` with untyped `metadata: Any` / `data: Any` | Loses type-checker benefit at domain knot boundaries; downstream knots require casts. |
| Protocol-based `HasMetadata` / `HasData` | No `isinstance(payload, Payload)` for the `PirnOpaqueValue` serialisation path. |

---

## ADR-2: Single-Repo, Optional-Extras-Per-Domain Packaging

### Context

Seven domain libraries each pull in heavy, often conflicting optional dependencies (scipy, MNE, segyio, lasio, xgboost, anthropic, polars, etc.). The original design considered separate installable packages per domain. Pirn's intended distribution model needed a firm decision before the first domain shipped.

### Decision

All domain libraries live under `pirn/domains/` in a single package. Each domain's extras are declared in `pyproject.toml` under `[project.optional-dependencies]` (e.g. `pirn[signal]`, `pirn[health]`, `pirn[ml]`). Each domain's `__init__.py` performs a guarded import and raises a descriptive `ImportError` with the install command if extras are absent.

Users install only what they need. A single `pirn[all]` extra exists for development and CI.

### Alternatives Rejected

| Alternative | Reason Rejected |
|-------------|----------------|
| Separate packages (`pirn-signal`, `pirn-health`, etc.) | Versioning, cross-domain shared types (`Payload`, `DataBatch`), and cross-domain pipeline composition become significantly harder to coordinate across separate release cycles. |
| Single package with all dependencies required | Bloated install for every user regardless of domain; conflicting deps (e.g. torch vs jax) would block installation entirely. |

### Consequences

- Shared types (`Payload`, `DataBatch`, `KnotRegistry`) live in `pirn/core/` and `pirn/domains/` at a level above any domain — importable with no extras.
- Cross-domain pipelines (e.g. signal → health) are composable in a single process with the appropriate extras installed.
- CI installs `pirn[all]` and runs all tests with extras present; tests that require missing extras use skip guards.

---

## ADR-3: Assembler / Disassembler Pattern

### Context

The original codebase used "ingestor" knots that combined I/O (connector logic) with domain parsing in a single class. This made knots hard to test in isolation, impossible to reuse across domains, and entangled connector configuration with domain logic.

### Decision

All ingestor knots were deleted. The connector–domain boundary is now a two-knot bridge:

- **Assembler** (`pirn/core/assembler.py`): receives raw connector output (bytes, rows, messages) and constructs a typed `Payload[M, D]`. No I/O in `process()`.
- **Disassembler** (`pirn/core/disassembler.py`): receives a `Payload[M, D]` and serialises it back to connector-ready form. No I/O in `process()`.

All seven domains have `assemblers/` and `disassemblers/` directories. Connector knots (Source, Sink) remain domain-agnostic; they are composed with assemblers/disassemblers in tapestries.

### Consequences

- Domain `process()` methods are fully testable in-process with no connector dependency.
- Connector knots are reusable across domains without modification.
- Type annotations at the boundary are precise: assembler return type is `Payload[SomeMetadata, SomeData]`.

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|-----------|
| Should `Payload` use `Generic[M, D]` or structural subtyping (Protocol)? | Nominal subtyping via `Generic[M, D]` — needed for `isinstance` check in the transport layer. |
| Should cross-tier bridging knots ship with this initiative? | No — deferred pending demonstrated user need. |
| Should domains ship as separate packages? | No — single package, optional extras. |
