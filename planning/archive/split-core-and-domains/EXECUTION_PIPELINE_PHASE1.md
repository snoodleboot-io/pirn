# Phase 1 Plan — Fold Connectors into Core (SCD-05, 06, 07)

**Fidelity:** SKELETON ⚠ — item list/deps/AC are stable (from `FEATURES.md`); execution detail marked `⚠ pending SCD-01` is re-presented before this phase runs.
**Inherits:** [PIPELINE.md](./PIPELINE.md) A–D.
**Depends on:** SCD-02 (workspace), and the **SCD-01 collision resolution** — `databaseconnectionpoolknot` and `messagebrokerknot` become core↔pirn-data cross-package collisions exactly here, so SCD-01 *must* have made them unique first.
**Issues:** [#56](https://github.com/snoodleboot-io/pirn/issues/56), [#57](https://github.com/snoodleboot-io/pirn/issues/57), [#58](https://github.com/snoodleboot-io/pirn/issues/58).

## Items & dependencies
```
SCD-05 (interfaces → pirn.connectors.*) → SCD-06 (backends + codecs behind extras) → SCD-07 (C2 import-graph gate)
SCD-07 also depends on SCD-05
```
Largely sequential (interfaces must land before backends move behind them); SCD-07's CI-gate authoring can draft in parallel with SCD-06.

## Delta §3 — Environment
Full docker test env (Postgres/Valkey/Redpanda/MinIO) + uv — SCD-06 moves ~80 backends and ~90 codecs, validated by `needs_postgres/valkey/kafka/s3` integration tests. Same manifest as the gate ([SCD-01 §3](./EXECUTION_PIPELINE_SCD01.md)).

## Delta §4 — Execution map
```mermaid
flowchart TD
    ENV[Env-Setup: uv + docker backends] --> S5["SCD-05 (refactor): move interface types<br/>(DatabaseConnectionPool, ObjectStore, MessageBroker, APIClient,<br/>FileFormat, ConnectionConfig, DsnScrubber, FileFormatRegistry)<br/>→ pirn.connectors.* · keep PirnOpaqueValue/DataTransport/SerializerRegistry on pirn.core.*"]
    S5 --> AGG5{{no interface top-imports a backend dep · 3 connector factory knots register at core import}}
    AGG5 --> S6["SCD-06 (refactor → category subagents): move backends (db/object/messaging/saas/<br/>bi_catalog/graph/timeseries/streaming/document/observability) + codecs<br/>behind core optional extras · lazy heavy imports"]
    S6 --> AGG6{{extras declared (postgres/s3/kafka/zstd/... + all-db/all-storage/all-stream)<br/>· bare pirn-core imports clean with zero backends}}
    AGG6 --> S7["SCD-07 (devops): C2 import-graph CI gate"]
    S7 --> AGG7{{CI fails if pirn imports any pirn_<domain> OR any backend pkg at import}}
    AGG7 --> GATES[G-ENF → G-SEC → G-REV] --> DEC[architect: confirm ADR-2 boundary] --> DONE([Phase 1 done])
```

## Delta §5 — Subagents `⚠ pending SCD-01`
- **SCD-05** (refactor): relocate 8 interface types to `packages/pirn-core/src/pirn/connectors/`, namespaced not flattened (ADR-2 open-q #5). `⚠` the registration mechanism for the 3 factory knots assumes the gate's `fill_registry` story.
- **SCD-06** (refactor, fan out by backend **category** — natural parallel lanes, worktree-isolated): each category subagent moves its backends + declares its extras + converts heavy imports to lazy (`try/except` / `ExtrasLoader.require()`). `numpy` serializer stays conditional.
- **SCD-07** (devops): import-graph check wired into required-checks.

## Delta §7 — Test strategy
ATDD: "bare `pirn-core` (no extras) imports clean with zero backend packages present" (SCD-06 AC#4) + C2 gate red-before/green-after. TDD: per-category lazy-import tests; each backend skips cleanly without its extra. Real-backend `needs_*` tests confirm moved backends still function.

## Delta §8 — Integration verification
Each moved backend tested against its live service (Postgres/Kafka/MinIO/Valkey). `pirn.connectors.*` public surface imports without pulling any backend. C2: import `pirn` in a bare venv → assert no asyncpg/aioboto3/kafka/zstandard imported.

## Delta §9 — Gaps `⚠`
- P1-A: SCD-06 is the largest move (~170 files). Fan-out by category keeps subagent scope bounded; aggregator merges worktrees.
- P1-B `⚠`: factory-knot registration depends on the gate's validated `fill_registry` behavior — provisional until SCD-01 closes.

## DoD (→ #56/#57/#58 AC)
- ☐ Interfaces import from `pirn.connectors.*`; `PirnOpaqueValue`/`DataTransport`/`SerializerRegistry` stay on `pirn.core.*`; no interface top-imports a backend; 3 factory knots register at core import. *(SCD-05)*
- ☐ All extras + aggregates declared in `pirn-core`; lazy heavy imports; conditional numpy; bare install imports clean. *(SCD-06)*
- ☐ CI fails on `pirn`→domain import or backend-at-import; runs every PR, in required checks. *(SCD-07)*
