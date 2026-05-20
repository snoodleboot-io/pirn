# ADR — Dataset Lineage

**Status:** Backlog  
**Date:** 2026-05-19  
**Related PRD:** `DATASET_LINEAGE_PRD.md`

---

## Context

Asset identity is already present in every assembler and disassembler — it's encoded in constructor arguments (paths, URIs, table names, connection strings). The question is how to surface it to the lineage system without breaking encapsulation or adding framework magic.

---

## Decision

**Add `source_dataset()` and `sink_dataset()` virtual methods to `Assembler` and `Disassembler` base classes respectively. The engine calls them post-execution via the existing `lineage_extra()` mechanism.**

This is the natural extension of the `lineage_extra()` pattern already in place for gate predicates, fan-out stats, and sub-tapestry metadata. No new engine machinery is needed.

---

## Approach

### Hook location: `Assembler` and `Disassembler`, not `DataTransport`

`DataTransport` is inter-knot plumbing — it moves outputs between knots within a run. It does not know about external assets. The assembler/disassembler boundary is the correct place: it is the explicit translation layer between the external world and the domain pipeline.

### Return type: `str | None`

A URI string is the lowest common denominator across all asset types (filesystem paths, S3 URIs, database connection strings + table names, object store paths). Structured types (a `DatasetRef` model) would be cleaner but add a new public type to the core API for marginal benefit at this stage. Can be evolved in a follow-on.

Format convention (not enforced, documented):
- Filesystem: `file:///abs/path/to/file.parquet`
- Object store: `s3://bucket/prefix/file.parquet` or `gs://...`
- Database table: `postgresql://host/db#schema.table`
- Valkey/Redis: `valkey://host:port/db#key`

### Engine wiring: via `lineage_extra()`

`Assembler.lineage_extra()` calls `super().lineage_extra()` and merges `{"source_dataset": self.source_dataset()}` when non-None. Same for `Disassembler`. The engine already calls `knot.lineage_extra()` — zero engine changes needed.

### Obligation on concrete classes

Each concrete assembler/disassembler overrides one method returning one string. This is intentionally low-friction. Classes that cannot determine a stable URI at construction time (e.g. dynamically routed connectors) return `None` — no penalty.

---

## Alternatives Considered

### A. Capture from `DataTransport`

Transport knows the physical location of intermediate knot outputs (the temp files, cache keys). But this is the inter-knot transport layer, not the external asset boundary. It would record pirn's own scratch space, not the user's data assets.  
**Rejected:** Wrong boundary.

### B. Structured `DatasetRef` type

Return a typed object with `uri`, `format`, `namespace`, `version` fields instead of a raw string.  
**Pro:** Queryable, extensible, consistent.  
**Con:** Adds a new public type to core. Can always be added in v2 by changing the return type — migration is non-breaking (string → model).  
**Deferred:** v2 if query patterns demand it.

### C. Connector knots declare the asset

Connector knots (the I/O layer below assemblers) already hold connection strings. Capture there instead.  
**Con:** Connectors are not in pirn core — they're domain/plugin code. The assembler is the first pirn-controlled boundary above the connector.  
**Rejected:** Wrong layer.

---

## Consequences

**Positive:**
- Zero engine changes.
- ~35 concrete classes each get one method override.
- Consistent with `lineage_extra()` pattern already established.
- Future: URI strings can be indexed for impact analysis queries.

**Negative / Trade-offs:**
- Requires updating every existing concrete assembler/disassembler — mechanical but non-trivial breadth (~35 classes across 5 domains).
- URI format is by convention, not enforced — inconsistent strings across domains are possible without a linter or validator.

---

## File Changes

```
pirn/core/assembler.py          ← add source_dataset() + lineage_extra()
pirn/core/disassembler.py       ← add sink_dataset() + lineage_extra()
pirn/domains/*/assemblers/*.py  ← override source_dataset() (~20 files)
pirn/domains/*/disassemblers/*.py ← override sink_dataset() (~15 files)
pirn/viz/explorer.py            ← render source_dataset / sink_dataset in knot detail
tests/unit/core/test_dataset_lineage.py
```
