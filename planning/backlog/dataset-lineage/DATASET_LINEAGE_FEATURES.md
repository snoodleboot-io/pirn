# Feature Breakdown — Dataset Lineage

**Status:** Backlog  
**Date:** 2026-05-19  
**Related:** `DATASET_LINEAGE_PRD.md`, `DATASET_LINEAGE_ADR.md`

---

## Task 1 — `Assembler` base: `source_dataset()` + `lineage_extra()`

**File:** `pirn/core/assembler.py`  
**Size:** XS

```python
def source_dataset(self) -> str | None:
    return None

def lineage_extra(self) -> dict[str, Any]:
    extra = super().lineage_extra()
    uri = self.source_dataset()
    if uri is not None:
        extra["source_dataset"] = uri
    return extra
```

**Acceptance:** `Assembler` subclass that does not override `source_dataset()` produces no `source_dataset` key in lineage extra.

---

## Task 2 — `Disassembler` base: `sink_dataset()` + `lineage_extra()`

**File:** `pirn/core/disassembler.py`  
**Size:** XS

Same pattern as Task 1, key `sink_dataset`.

**Acceptance:** `Disassembler` subclass that does not override produces no `sink_dataset` key.

---

## Task 3 — Health domain assemblers (~5 classes)

**Files:** `pirn/domains/health/assemblers/*.py`  
**Size:** S

| Class | URI pattern |
|---|---|
| `DicomPacsAssembler` | `dicom://host/ae#study_uid` |
| `FhirPatientAssembler` | `fhir://host/Patient` |
| `EegObjectStoreAssembler` | object store URI from config |
| `MegObjectStoreAssembler` | object store URI from config |
| `WsiObjectStoreAssembler` | object store URI from config |

Also `EncounterTimelineAssembler` in `health/clinical/`.

---

## Task 4 — Health domain disassemblers (~4 classes)

**Files:** `pirn/domains/health/disassemblers/*.py`  
**Size:** S

`DicomObjectStoreDisassembler`, `EegObjectStoreDisassembler`, `MegObjectStoreDisassembler`, `WsiObjectStoreDisassembler`.

---

## Task 5 — ML domain assemblers + disassemblers (~5 classes)

**Files:** `pirn/domains/ml/assemblers/*.py`, `pirn/domains/ml/disassemblers/*.py`  
**Size:** S

| Class | URI pattern |
|---|---|
| `TrainedModelObjectStoreAssembler` | object store URI |
| `DatasetObjectStoreDisassembler` | object store URI |
| `DataSplitObjectStoreDisassembler` | object store URI |
| `EvalReportDatabaseDisassembler` | database URI + table |
| `TrainedModelObjectStoreDisassembler` | object store URI |

---

## Task 6 — Oil & Gas domain assemblers + disassemblers (~7 classes)

**Files:** `pirn/domains/oilgas/assemblers/*.py`, `pirn/domains/oilgas/disassemblers/*.py`  
**Size:** S

`LasObjectStoreAssembler`, `MudLogAssembler`, `ScadaDatabaseAssembler`, `SegyObjectStoreAssembler`, `WellCompletionObjectStoreAssembler`, `LasObjectStoreDisassembler`, `SegyObjectStoreDisassembler`.

---

## Task 7 — Signal domain assemblers + disassemblers (~4 classes)

**Files:** `pirn/domains/signal/assemblers/*.py`, `pirn/domains/signal/disassemblers/*.py`  
**Size:** S

`SignalObjectStoreAssembler`, `SignalObjectStoreDisassembler`, `SpectrumObjectStoreDisassembler`, `WaveletObjectStoreDisassembler`.

---

## Task 8 — Connector transport assemblers (2 classes)

**Files:** `pirn/domains/connectors/transports/*.py`  
**Size:** XS

`ValkeyTransport`, `ObjectStoreTransport` — if these are assembler/disassembler subclasses, add overrides. If connector knots (not assemblers), skip.

---

## Task 9 — Explorer: render `source_dataset` / `sink_dataset`

**File:** `pirn/viz/explorer.py`  
**Size:** S

In the knot detail panel extra metadata section, render `source_dataset` and `sink_dataset` with a distinct style (e.g. link-like, monospace path). These are the most important extra fields for human readers.

---

## Task 10 — Unit tests

**File:** `tests/unit/core/test_dataset_lineage.py`  
**Size:** S

| Test | Covers |
|---|---|
| `test_assembler_default_returns_none` | Base class produces no key |
| `test_assembler_override_captured` | Concrete override appears in lineage extra |
| `test_disassembler_default_returns_none` | Same for sink |
| `test_disassembler_override_captured` | Same |
| `test_plain_knot_unaffected` | Non-assembler knot has no dataset keys |

---

## Dependency Graph

```
Tasks 1–2 (base classes)
  └── Tasks 3–8 (domain concrete classes, parallelisable)
        └── Task 9 (explorer)
              └── Task 10 (tests — can start after Tasks 1–2)
```

---

## Estimated Total

| Size | Count | Rough LOC |
|---|---|---|
| XS | 3 | ~30 |
| S | 7 | ~140 |
| **Total** | **10** | **~170** |
