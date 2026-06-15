# Assembler and Disassembler Knots

This document defines the Assembler/Disassembler pattern — the required bridge between
pirn's connector layer (which deals in raw Python types) and domain knots (which deal
in typed `Payload` subclasses).

Read and follow every convention here — these are enforced in code review:

- One class per file, no exceptions.
- No module-level constants.
- Assemblers and disassemblers must not perform I/O.
- Methods belong to classes; no module-level functions (use `@staticmethod` inside the
  class instead).

---

## Background

pirn connector knots produce and consume raw Python types:

- `ObjectStoreReadSource` → `bytes`
- `DatabaseQuerySource` → `list[tuple[Any, ...]]`
- `ObjectStoreListSource` → `list[str]`
- `ObjectStoreWriteSink` ← `bytes`
- `DatabaseExecuteSink` ← `list[tuple[Any, ...]]`

Domain knots produce and consume typed `Payload` subclasses:

- `SignalPayload`, `LASPayload`, `ScadaPayload`, `DICOMPayload`, etc.

Nothing in the framework bridges these two worlds automatically. That bridge is the
responsibility of **Assembler** and **Disassembler** knots.

---

## Definitions

### Assembler

An Assembler knot converts raw connector output into a domain `Payload`.

- **Input:** raw types — `bytes`, `list[tuple]`, `list[dict]`, etc.
- **Output:** a `Payload[M, D]` subclass
- **Location:** `pirn/domains/{domain}/assemblers/{name}.py`
- **Naming:** `{Subject}{Source}Assembler`
  - `SignalObjectStoreAssembler` — bytes from an object store → `SignalPayload`
  - `ScadaDatabaseAssembler` — rows from a database → `ScadaPayload`
  - `FhirPatientAssembler` — record dicts from a FHIR client → `tuple[ClinicalRecord, ...]`

### Disassembler

A Disassembler knot converts a domain `Payload` into raw types for a connector sink.

- **Input:** a `Payload[M, D]` subclass
- **Output:** raw types — `bytes`, `list[tuple]`, etc.
- **Location:** `pirn/domains/{domain}/disassemblers/{name}.py`
- **Naming:** `{Subject}{Sink}Disassembler`
  - `TrainedModelObjectStoreDisassembler` — `TrainedModelPayload` → `bytes` for object store

---

## When an Assembler or Disassembler is Required

**Required** at every point where a domain Payload crosses into or out of raw connector
I/O. Concretely: any time a domain knot's `process()` would need to accept `bytes`,
`list[tuple]`, or a raw connector client object in order to produce a Payload, an
Assembler must sit between the connector knot and that domain knot.

**Not required** for ETL knots that perform an atomic read-transform-write cycle against
a pool or broker. These knots own their I/O by design — splitting them would break
atomicity. Examples: `ScdType2`, `MergeUpsert`, `CDCDebezium`. See `data/specializations/`
for the canonical examples.

**Not required** for `data/sources/` knots (`FileSource`, `SqlSource`, `DirectorySource`)
— these are already the assembler layer for `DataBatch`.

---

## The Ingestor Anti-Pattern

Before this pattern was codified, domain knots called "ingestors" collapsed the I/O and
assembly steps into one `process()` method — accepting a raw file path or connection
object and producing a Payload:

```python
# WRONG — ingestor anti-pattern
class AudioFileIngestor(Knot):
    async def process(self, path: str, ...) -> SignalPayload:
        y, sr = librosa.load(path, sr=None, mono=False)  # I/O inside process()
        return SignalPayload(metadata=..., data=y)
```

This is wrong because:

1. `process()` cannot be tested without a real file on disk.
2. The I/O concern (read bytes from storage) is coupled to the domain concern (interpret
   bytes as a `SignalPayload`).
3. The connector layer cannot be reused across domains.

The correct pattern splits this into two knots:

```
ObjectStoreReadSource(store=..., key="audio/clip.wav")
    ↓ bytes
SignalObjectStoreAssembler(body=..., ...)
    ↓ SignalPayload
(downstream domain knots)
```

Ingestors are not refactored — they are deleted and replaced by the corresponding
Assembler.

---

## Assembler Contract

Every Assembler must:

1. Extend `Assembler` from `pirn.core.assembler` (not `Knot` or `Source` directly).
2. Declare `process()` with the raw input type(s) as parameters and return a `Payload`
   subclass.
3. Include `**_: Any` in `process()`.
4. Raise `TypeError` before `ValueError` when validating inputs (type check first,
   value check second).
5. Perform **no I/O** — it receives already-materialised raw values from its connector
   parent knot.
6. Construct and return the Payload entirely from its inputs.

```python
class SignalObjectStoreAssembler(Assembler):
    """Assemble a :class:`SignalPayload` from raw audio bytes."""

    def __init__(
        self,
        *,
        body: Knot,
        signal_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(body=body, signal_id=signal_id, _config=_config, **kwargs)

    async def process(
        self,
        body: bytes,
        signal_id: str,
        **_: Any,
    ) -> SignalPayload:
        if not isinstance(body, bytes):
            raise TypeError("SignalObjectStoreAssembler: body must be bytes")
        if not isinstance(signal_id, str) or not signal_id:
            raise ValueError("SignalObjectStoreAssembler: signal_id must be a non-empty string")
        # decode bytes and construct Payload — no file I/O here
        ...
        return SignalPayload(metadata=frame, data=samples)
```

---

## Disassembler Contract

Every Disassembler must:

1. Extend `Disassembler` from `pirn.core.disassembler`.
2. Declare `process()` accepting a `Payload` subclass and returning raw types.
3. Include `**_: Any` in `process()`.
4. Raise `TypeError` / `ValueError` for invalid input.
5. Perform **no I/O**.

```python
class TrainedModelObjectStoreDisassembler(Disassembler):
    """Serialise a :class:`TrainedModelPayload` to raw bytes for object store upload."""

    def __init__(self, *, payload: Knot, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(payload=payload, _config=_config, **kwargs)

    async def process(self, payload: TrainedModelPayload, **_: Any) -> bytes:
        if not isinstance(payload, TrainedModelPayload):
            raise TypeError("TrainedModelObjectStoreDisassembler: payload must be a TrainedModelPayload")
        # serialise — no I/O
        ...
        return serialized_bytes
```

---

## Reference Implementations

The canonical examples of this pattern in the codebase are:

- `pirn_data/specializations/medallion/tuples_to_data_batch_knot.py`
  (`TuplesToDataBatchKnot`) — Assembler: `list[tuple]` → `DataBatch`
- `pirn_data/specializations/medallion/data_batch_to_tuples_knot.py`
  (`DataBatchToTuplesKnot`) — Disassembler: `DataBatch` → `list[tuple]`

Note: `TuplesToDataBatchKnot` and `DataBatchToTuplesKnot` predate the `Assembler`/`Disassembler` base classes and extend `Knot` directly. They are the conceptual reference for the pattern, but do not demonstrate the required base class inheritance. For implementation, follow the pattern of any knot in `pirn/domains/{domain}/assemblers/` or `pirn/domains/{domain}/disassemblers/` — these all correctly extend `Assembler` or `Disassembler`.

Read these before writing a new Assembler or Disassembler.

---

## Folder Layout

```
pirn/domains/{domain}/
    assemblers/
        __init__.py
        {subject}_{source}_assembler.py
    disassemblers/
        __init__.py
        {subject}_{sink}_disassembler.py
```

Both `__init__.py` files must be present. They are empty — no re-exports.

---

## Tests

For every Assembler and Disassembler, write unit tests covering:

- Valid input → correct `Payload` type returned with correct metadata fields
- Invalid type input → `TypeError` with correct message
- Invalid value input → `ValueError` with correct message

Tests must not touch the file system, network, or any connector. All inputs are
constructed in-process.
