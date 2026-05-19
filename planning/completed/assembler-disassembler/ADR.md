# ADR: Assembler / Disassembler Pattern

Status: Accepted | Date: 2026-05-15

---

## Context

Domain ingestors collapsed I/O and domain parsing into one `process()` — accepting a file path or connection object and producing a `Payload`. This violated single-responsibility in three ways: (1) `process()` could not be tested without a real file on disk, (2) the I/O concern was coupled to the domain concern, and (3) connector knots could not be reused across domains. Connector knots already produced raw Python types (`bytes`, `list[tuple]`, `list[dict]`). Domain knots needed typed `Payload` subclasses. Nothing bridged them.

---

## Decision

Delete all ingestors. Replace them with two new knot classes:

**Assembler** — raw bytes / rows → `Payload[M, D]`. No I/O. Receives already-materialised values from a connector parent knot. Base class: `pirn.core.assembler.Assembler(Knot)`.

**Disassembler** — `Payload[M, D]` → raw bytes / rows. No I/O. Produces raw values for a connector sink knot. Base class: `pirn.core.disassembler.Disassembler(Knot)`.

Both base classes are thin markers — no additional logic. They let tooling, type checkers, and reviewers identify assembler/disassembler knots at a glance. The `process()` contract is still enforced by `Knot.__init_subclass__`.

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

Naming convention: `{Subject}{Source}Assembler` and `{Subject}{Sink}Disassembler`. Files live in `pirn/domains/{domain}/assemblers/` and `pirn/domains/{domain}/disassemblers/`.

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
- `process()` of every Assembler and Disassembler is testable in-process with no file system, network, or connector access.
- Connector knots are fully reusable across domains — `ObjectStoreReadSource` feeds any Assembler regardless of domain.
- Single-responsibility is enforced structurally, not by convention.
- `TypeError` before `ValueError` contract makes validation failures explicit and ordered.

**Negative:**
- Two-knot wiring (connector + assembler) adds verbosity compared to a single ingestor for simple cases.
- All existing ingestors required deletion and replacement — a one-time migration cost across all seven domains (completed 2026-05-15).
