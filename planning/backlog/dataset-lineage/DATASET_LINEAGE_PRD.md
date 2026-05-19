# PRD — Dataset Lineage

**Status:** Backlog  
**Date:** 2026-05-19  
**Author:** John Aven

---

## Problem Statement

Every pirn run records which knots executed and whether they succeeded, but not **what external data assets were touched**. There is no record of which files, tables, object store paths, or databases a pipeline read from or wrote to. This makes it impossible to answer "which runs touched `orders.parquet`?" or "what did this run write?" from history.

The model has a clear structural boundary where this information already lives: `Assembler` knots sit at every source boundary (connector → domain pipeline) and `Disassembler` knots sit at every sink boundary (domain pipeline → connector). Both already encode the asset identity implicitly in their construction — they just don't surface it to lineage.

---

## Goals

1. Every `Assembler` knot records the URI/path/table of the asset it read from.
2. Every `Disassembler` knot records the URI/path/table of the asset it wrote to.
3. Asset references are stored per-knot in `KnotLineage` and queryable from run history.
4. The explorer displays input/output datasets per knot in the detail panel.
5. Knots that are neither assemblers nor disassemblers produce no dataset lineage — no noise, no obligation.
6. The contract is low-friction: one method override per concrete class, returning a URI string.

---

## Non-Goals

- Column-level lineage — tracked separately in the column-lineage initiative.
- Value/record-level lineage — deferred indefinitely.
- Connector knots themselves (source/sink I/O) — asset identity is declared on the assembler/disassembler that wraps them, not the connector.
- Retroactive backfill of existing history.

---

## User Stories

**Pipeline author**
> As a data engineer, I want to declare the asset URI my assembler reads from once, so that every run automatically records which file or table was the source.

**Audit user**
> As someone reviewing run history, I want to see "this knot read from `s3://bucket/orders/2026-05-01.parquet`" in the explorer, so I can trace data provenance without reading the code.

**Impact analysis**
> As a platform engineer, I want to query history and find all runs that touched a specific table or path, so I can assess the blast radius of a schema change.

---

## Functional Requirements

| # | Requirement |
|---|---|
| F-1 | `Assembler` gains a `source_dataset() -> str \| None` virtual method; default returns `None`. |
| F-2 | `Disassembler` gains a `sink_dataset() -> str \| None` virtual method; default returns `None`. |
| F-3 | Engine calls `source_dataset()` / `sink_dataset()` post-execution and includes the result in `KnotLineage` via `lineage_extra()`. Keys: `source_dataset`, `sink_dataset`. |
| F-4 | All existing concrete assemblers (~20) and disassemblers (~15) override the appropriate method, returning their asset URI. |
| F-5 | The explorer's knot detail panel displays `source_dataset` and `sink_dataset` when present. |
| F-6 | No changes required on knots that are neither assemblers nor disassemblers. |

---

## Acceptance Criteria

- [ ] `ScadaDatabaseAssembler.source_dataset()` returns the database URI/table it targets.
- [ ] `LasObjectStoreDisassembler.sink_dataset()` returns the object store path it writes to.
- [ ] A plain `Knot` subclass has no `source_dataset` or `sink_dataset` in its lineage extra.
- [ ] Explorer shows dataset refs in the knot detail panel for assembler/disassembler knots.
- [ ] All existing tests pass with no changes to test code.
- [ ] New unit tests cover the virtual method contract and engine wiring.
