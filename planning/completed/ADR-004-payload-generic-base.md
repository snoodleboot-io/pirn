# ADR-004: Payload[M, D] — Generic Base for All Domain Payload Types

**Status:** Accepted
**Date:** 2026-05-15
**Branch:** feat/domain-gap-remediation-plan
**Source:** pirn/core/payload.py

---

## Context

Domain knots need to carry two things through the pirn transport layer:

1. **Metadata** — a typed descriptor that provides provenance, lineage, and structural context (e.g. `SignalFrame`, `LASFile`, `DICOMSeries`). Generic code and the audit trail operate against this.
2. **Data** — the actual computation result (numpy arrays, fitted models, metric dicts, raw waveforms, etc.). Domain knots operate against this.

Before the `Payload` base class was introduced, some domain knots passed metadata-only types through the pipeline — the data buffer was absent, or both metadata and data were collapsed into a single untyped dict. This made it impossible for downstream knots to distinguish "I have the data" from "I have a description of the data."

The assembler/disassembler pattern (ADR-001) required a single typed base that any assembler could return and any domain knot could accept, regardless of domain. Without a common base, type annotations across the connector–domain boundary were `Any`.

---

## Decision

Introduce `Payload[M, D]` in `pirn/core/payload.py` as the generic base class for all domain payload types.

```python
class Payload(PirnOpaqueValue, Generic[M, D]):
    def __init__(self, metadata: M, data: D) -> None: ...

    @property
    def metadata(self) -> M: ...   # generic accessor for audit / transport code

    @property
    def data(self) -> D: ...       # generic accessor for generic code

    def _pirn_audit_dict(self) -> dict[str, Any]: ...
    # delegates to metadata._pirn_audit_dict() — audit trail stays in one place
```

Concrete subclasses expose domain-readable aliases as read-only properties backed by `_metadata` / `_data`. Examples:

- `SignalPayload(Payload[SignalFrame, np.ndarray])` — exposes `.frame` and `.samples`
- `ScadaPayload(Payload[ScadaMetadata, np.ndarray])` — exposes `.series` and `.values`
- `TrainedModelPayload(Payload[ModelMetadata, Any])` — exposes `.model_metadata` and `.estimator`

Generic code (transport, serialisation, audit) programs against `.metadata` / `.data`. Domain knots use the semantic property names.

**Serialisation:** `_pirn_audit_dict` delegates entirely to `metadata._pirn_audit_dict()`. Transport round-trips use pickle via `PickleSerializer` fallback in `SerializerRegistry`. The audit dict is never used for reconstruction.

**Inheritance chain:** `Payload` extends `PirnOpaqueValue`, which signals to the framework that this type is an opaque value (not introspected by the engine for field extraction).

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| Typed dataclasses per domain with no shared base | No common type for assembler return annotations or generic transport code. Type checker cannot verify that an assembler returns something the framework knows how to handle. |
| Single `Payload` with untyped `metadata: Any` and `data: Any` | Loses the type-checker benefit at domain knot boundaries — downstream knots would need casts. |
| Protocol-based `HasMetadata` / `HasData` | Structural subtyping works but does not allow `isinstance(payload, Payload)` checks in the transport layer, which is needed for the `PirnOpaqueValue` serialisation path. |

---

## Consequences

**Positive:**
- Every assembler has a precise return type: `Payload[SomeMetadata, SomeData]`.
- Every domain knot's `process()` parameter type is checkable at the call site.
- The audit trail is always driven by `metadata._pirn_audit_dict()` — one place to look.
- Generic transport and serialisation code works against `Payload` without domain knowledge.

**Negative:**
- Concrete subclasses must define property aliases (`frame`, `samples`, etc.) — minor boilerplate per payload type.
- `PickleSerializer` fallback means payloads carrying non-picklable objects (e.g. open file handles) will fail at transport. Domain knots are responsible for ensuring `data` is picklable.

---

## Payload Audit (2026-05-15)

The payload pattern audit confirmed that the three highest-traffic domains pass:

- **agents:** `AgentContext`, `AgentResponse`, `ToolResult` are typed immutable dataclasses. No metadata-only types cross pipeline boundaries bare.
- **data:** `DataBatch` (and `PandasDataBatch`, `PolarsDataBatch`) carry both schema metadata and the actual DataFrame. Sources correctly materialise into `DataBatch` with schema, URI, and timestamp.
- **connectors:** IO knots (`ObjectStoreReadSource` → `bytes`, `MessageBrokerPublishSink` → `None`) are correct at this level. `FileSource` composes ObjectStore + FileFormat → `DataBatch` correctly.
