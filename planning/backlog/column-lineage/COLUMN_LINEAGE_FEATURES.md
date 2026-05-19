# Feature Breakdown — Column Lineage

**Status:** Backlog  
**Date:** 2026-05-19  
**Note:** PRD and ADR to be written when this initiative is promoted to current. Breakdown captured now to scope the work.

---

## Summary

Column lineage tracks which input columns map to which output columns through each knot. The approach is tier-aware: higher tiers get automatic extraction from query plans; lower tiers get a voluntary virtual method. No tier is forced — absence of column lineage is never an error.

---

## Tier Map

| Tier | Engine | Extraction method |
|---|---|---|
| Tier 1 — raw Python | Any `Knot` | Virtual method `column_lineage()` — manual, optional |
| Tier 2 — DataFrames | Polars, Pandas | Schema capture at input + output boundary; rename/drop detection |
| Tier 2.5 — OOC | Dask, Modin | Same as Tier 2 |
| Tier 3 — push-down | Ibis, DataFusion | Query plan walk — automatic column provenance |
| Tier 3-stream | Kafka, Flink | Schema registry lookup at source/sink |
| Tier 4 — specialized | cuDF, JAX | Best-effort schema capture; no plan walking |

---

## Feature 1 — `ColumnLineage` model and `column_lineage()` base contract

**Files:** `pirn/core/column_lineage.py`, `pirn/core/knot.py`  
**Size:** S

Define:
```python
@dataclass(frozen=True)
class ColumnMapping:
    source_column: str
    target_column: str
    transform: str | None = None  # optional human-readable description

@dataclass(frozen=True)
class ColumnLineage:
    mappings: list[ColumnMapping]
```

Add virtual method to `Knot`:
```python
def column_lineage(self) -> ColumnLineage | None:
    return None
```

Engine calls post-execution, stores in `KnotLineage` extra as `column_lineage` key (serialised). Default `None` produces no key — no noise.

---

## Feature 2 — Tier 2: Polars schema capture

**Files:** `pirn/domains/data/frames/polars/` base knots  
**Size:** M

At Polars knot execution boundary:
- Capture `input_schema: dict[str, DataType]` before `process()` runs
- Capture `output_schema: dict[str, DataType]` after
- Compute: columns present in both with same name → `pass-through`; columns in output only → `derived`; columns in input only → `dropped`
- Build `ColumnLineage` automatically; no author intervention needed

**Limitation:** Cannot detect `revenue = price * quantity` as a derivation from two sources — reports `revenue` as `derived` with no mapping. Accurate for renames and pass-throughs; honest about derived columns.

---

## Feature 3 — Tier 2.5: Dask / Modin (same as Tier 2)

**Files:** Dask and Modin base knots in data domain  
**Size:** S

Same schema capture pattern as Tier 2. Dask and Modin expose `.dtypes` / `.schema` at the partition level — collect at the knot boundary, not inside partitions.

---

## Feature 4 — Tier 3: Ibis query plan extraction

**Files:** `pirn/domains/data/frames/ibis/` base knots  
**Size:** L

Ibis exposes a relational expression tree. Walk the tree to extract:
- Column references (direct pass-throughs and renames)
- Derived columns (function applications — record as `derived`)
- Aggregations (group keys and aggregation targets)

Ibis's `expr.op()` tree is the extraction point. This is the richest lineage source — it can name the specific input columns that feed a computed output column.

---

## Feature 5 — Tier 3: DataFusion query plan extraction

**Files:** `pirn/domains/data/frames/datafusion/` base knots  
**Size:** L

DataFusion's Python bindings expose a logical plan via `plan.to_proto()` or the `Expr` tree. Walk the projection list to extract column mappings. Similar richness to Ibis but different API surface.

---

## Feature 6 — Tier 3-stream: Schema registry integration

**Files:** Kafka/Flink connector knots in connectors domain  
**Size:** M

For streaming sources, schema is declared in a schema registry (Confluent Schema Registry or equivalent). At knot construction, look up the schema for the topic/stream URI and record it as the column list. No plan walking — schemas are declared, not inferred.

---

## Feature 7 — Tier 4: cuDF / JAX best-effort

**Files:** cuDF and JAX base knots  
**Size:** S

cuDF mirrors Pandas API — schema capture same as Tier 2. JAX operates on tensors not named columns — record tensor shape and dtype only; no column names. Honest about the limitation.

---

## Feature 8 — Engine wiring: `column_lineage()` call + storage

**Files:** `pirn/engine/engine.py`, `pirn/core/lineage.py`  
**Size:** S

Post-execution, engine calls `knot.column_lineage()`. If non-None, serialise to JSON and store in `KnotLineage` extra (or as a dedicated field — decision for ADR). For Tier 2–4 knots where extraction is automatic, the tier base class populates this before `column_lineage()` is called.

---

## Feature 9 — Explorer: column lineage panel

**Files:** `pirn/viz/explorer.py`  
**Size:** M

In the knot detail panel, render a column mapping table when `column_lineage` is present:

```
source_column    →    target_column    [transform]
─────────────────────────────────────────────────
order_id         →    order_id         pass-through
price * qty      →    revenue          derived
```

---

## Feature 10 — Unit tests

**Files:** `tests/unit/core/test_column_lineage.py`, per-tier tests  
**Size:** M

| Test scope | Covers |
|---|---|
| `ColumnMapping` / `ColumnLineage` model | Frozen, serialisable |
| Base `Knot.column_lineage()` | Returns None by default |
| Polars schema capture | Pass-through, rename, drop, derived |
| Ibis plan walk | Direct column ref, rename, aggregation |
| DataFusion plan walk | Projection extraction |
| Engine wiring | Non-None lineage stored; None produces no key |

---

## Dependency Graph

```
Feature 1 (model + base contract)
  └── Feature 8 (engine wiring)
        ├── Features 2–7 (tier implementations, parallelisable)
        └── Feature 9 (explorer)
              └── Feature 10 (tests — unit tests for F1 can start immediately)
```

---

## Estimated Total

| Size | Count | Rough LOC |
|---|---|---|
| S | 5 | ~250 |
| M | 3 | ~300 |
| L | 2 | ~300 |
| **Total** | **10** | **~850** |

This is the largest lineage initiative. L-sized items (Ibis and DataFusion plan walking) require deep familiarity with each engine's AST/expression API.
