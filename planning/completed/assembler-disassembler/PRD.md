# PRD: Assembler / Disassembler Pattern

Status: Complete | Completed: 2026-05-15

---

## Problem

Domain knots called "ingestors" collapsed I/O and domain parsing into a single `process()` method — accepting a raw file path or connection object and producing a `Payload` in one step. This made `process()` untestable without real files or network access, coupled the I/O concern (read bytes from storage) to the domain concern (interpret those bytes as a typed Payload), and prevented connector knots from being reused across domains. Every ingestor owned its own connection logic.

Connector knots already existed and produced raw Python types (`bytes`, `list[tuple]`, `list[dict]`). Domain knots needed typed `Payload` subclasses. Nothing bridged them.

---

## Goal

Replace ingestors with two new pure-function knot classes — Assembler and Disassembler — that handle raw↔Payload conversion with no I/O. The connector knot handles I/O; the assembler/disassembler handles domain interpretation. Every conversion knot must be testable in-process.

---

## Success Criteria (all met)

- `pirn/core/assembler.py` and `pirn/core/disassembler.py` ship as marker base classes extending `Knot`.
- Every assembler and disassembler `process()` is testable without file system or network access.
- Connector knots are fully reusable across domains — `ObjectStoreReadSource` feeds any assembler regardless of domain.
- `TypeError` is raised before `ValueError` in all input validation paths.
- All ingestors across all seven domains deleted and replaced by assembler knots.
- Assemblers and disassemblers present in signal, oilgas, health, and ml domains.
- Convention document at `docs/contributing/assembler-disassembler-pattern.md` codifies naming, location, and contract rules.

---

## Scope

### Domains covered

signal, oilgas, health, ml

### Ingestors deleted

| Domain | Deleted ingestors |
|--------|------------------|
| signal | `AudioFileIngestor` |
| oilgas | `LasFileIngester`, `SegyFileIngester`, `ScadaHistorianIngester`, `MudLoggingIngester`, `WellCompletionIngester` |
| health | `EEGRawIngestor`, `MegRawIngestor`, `DICOMIngestor`, `WsiTileExtractor`, `FhirPatientIngestor` |
| ml | none (ModelRegistrar and Predictor are legitimate sink/domain knots; ml gaps were net-new disassemblers) |

### Assemblers created

signal: `SignalObjectStoreAssembler`
oilgas: `LasObjectStoreAssembler`, `SegyObjectStoreAssembler`, `ScadaDatabaseAssembler`, `MudLogAssembler`, `WellCompletionObjectStoreAssembler`
health: `EegObjectStoreAssembler`, `MegObjectStoreAssembler`, `DicomPacsAssembler`, `WsiObjectStoreAssembler`, `FhirPatientAssembler`
ml: `TrainedModelObjectStoreAssembler`

### Disassemblers created

signal: `SignalObjectStoreDisassembler`, `SpectrumObjectStoreDisassembler`, `WaveletObjectStoreDisassembler`
oilgas: `LasObjectStoreDisassembler`, `SegyObjectStoreDisassembler`
health: `EegObjectStoreDisassembler`, `MegObjectStoreDisassembler`, `DicomObjectStoreDisassembler`, `WsiObjectStoreDisassembler`
ml: `TrainedModelObjectStoreDisassembler`, `DatasetObjectStoreDisassembler`, `DataSplitObjectStoreDisassembler`, `EvalReportDatabaseDisassembler`

### Out of scope

ETL specialisations in `data/specializations/` that perform atomic read-transform-write cycles against database pools are exempt — they own their I/O by design. `FileSource`, `SqlSource`, and `DirectorySource` in `data/sources/` are already the assembler layer for `DataBatch` and required no changes.
