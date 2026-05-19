# Lineage Capture — Shipped

**Branch:** feat/update-lineage-capture-and-correct-examples  
**Date:** 2026-05-19

## What shipped

- `lineage_extra()` virtual method on `Knot` — replaces getattr/setattr hacks; each class encapsulates its own execution metadata via virtual dispatch
- `KnotSourceRecord` — content-addressed source code snapshots stored in `knot_sources` SQLite table
- Gate, Branch, SubTapestry structured metadata in lineage extra (predicate_passed, selected_branch, inner_run_id, fan-out stats)
- Explorer: extra metadata panel per knot (error_policy, predicate_passed, map stats, inner run info)
- Explorer: source code modal with syntax highlighting (highlight.js)
- Scanner: batch-fetches knot_sources; exposes source_hash and extra per knot in run payload
- Transport layers example (E-3)
- Fixed examples for new SubTapestry contract
