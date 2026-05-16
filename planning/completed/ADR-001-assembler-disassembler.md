# ADR-001: Assembler / Disassembler Pattern

**Status:** Accepted
**Date:** 2026-05-15
**Branch:** feat/domain-gap-remediation-plan
**Source:** docs/contributing/assembler-disassembler-pattern.md

---

## Context

Before this pattern was codified, domain knots called "ingestors" collapsed I/O and
domain parsing into a single `process()` method — accepting a raw file path or connection
object and producing a `Payload`. Example:

```python
class AudioFileIngestor(Knot):
    async def process(self, path: str) -> SignalPayload:
        y, sr = librosa.load(path, sr=None, mono=False)  # I/O inside process()
        return SignalPayload(metadata=..., data=y)
```

This pattern violated single-responsibility in three ways:

1. `process()` could not be tested without a real file on disk.
2. The I/O concern (read bytes from storage) was coupled to the domain concern (interpret
   bytes as a typed `Payload`).
3. Connector knots could not be reused across domains — each ingestor owned its own
   connection logic.

Connector knots already existed and produced raw Python types (`bytes`, `list[tuple]`,
`list[dict]`). Domain knots needed typed `Payload` subclasses. Nothing bridged them.

---

## Decision

Replace all ingestors with two new knot classes: **Assembler** and **Disassembler**.

- **Assembler** — raw bytes / rows → `Payload[M, D]`. No I/O. Receives already-materialised values from a connector parent knot.
- **Disassembler** — `Payload[M, D]` → raw bytes / rows. No I/O. Produces raw values for a connector sink knot.

All existing ingestor knots are deleted, not refactored. The connector knot handles I/O;
the assembler/disassembler handles domain interpretation.

Pipeline wiring before and after:

```
# Before (ingestor anti-pattern)
AudioFileIngestor(path="audio/clip.wav") → downstream

# After
ObjectStoreReadSource(store=..., key="audio/clip.wav")
    ↓ bytes
SignalObjectStoreAssembler(body=..., signal_id=...)
    ↓ SignalPayload
downstream domain knots
```

Base classes `Assembler` and `Disassembler` live in `pirn.core.assembler` and
`pirn.core.disassembler` respectively. Both extend `Knot`.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| Refactor ingestors in-place to remove I/O | Each ingestor required understanding its specific I/O path; mechanical refactor at scale was error-prone. Deletion and fresh implementation was safer and enforced the new contract from the start. |
| Generic bridge in the framework (auto-convert bytes to Payload) | Too magical — the framework cannot know which domain format bytes represent without explicit domain logic. |
| Keep ingestors, add optional assembler layer | Creates two valid patterns simultaneously, making code review enforcement impossible. |

---

## Consequences

**Positive:**
- `process()` of every Assembler and Disassembler is testable in-process with no file
  system, network, or connector access.
- Connector knots are fully reusable across domains — `ObjectStoreReadSource` feeds
  any Assembler regardless of domain.
- Single-responsibility is enforced structurally, not by convention.
- `TypeError` before `ValueError` contract makes validation failures explicit and ordered.

**Negative / Risks:**
- Two-knot wiring (connector + assembler) adds verbosity compared to a single ingestor
  for simple cases.
- All existing ingestors required deletion and replacement — a one-time migration cost
  across all seven domains.

---

## Implementation

**Base class locations:**
- `pirn/core/assembler.py` — `Assembler` base class
- `pirn/core/disassembler.py` — `Disassembler` base class

**Domain assembler/disassembler locations:**
```
pirn/domains/{domain}/
    assemblers/
        __init__.py      (empty — no re-exports)
        {subject}_{source}_assembler.py
    disassemblers/
        __init__.py      (empty — no re-exports)
        {subject}_{sink}_disassembler.py
```

**Naming convention:**
- Assembler: `{Subject}{Source}Assembler` — e.g. `SignalObjectStoreAssembler`, `ScadaDatabaseAssembler`
- Disassembler: `{Subject}{Sink}Disassembler` — e.g. `TrainedModelObjectStoreDisassembler`

**Reference implementations (predate base classes, extend `Knot` directly):**
- `pirn/domains/data/specializations/medallion/tuples_to_data_batch_knot.py`
- `pirn/domains/data/specializations/medallion/data_batch_to_tuples_knot.py`

**Contract requirements (enforced in code review):**
- One class per file
- No module-level constants
- No I/O in `process()`
- Methods belong to classes — no module-level functions
- `TypeError` raised before `ValueError` when validating inputs
- `**_: Any` included in `process()` signature

**Phases 1–5 of assembler/disassembler implementation completed 2026-05-15** across all
seven domains. All ingestors deleted.
