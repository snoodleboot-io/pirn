# Planning

Each initiative has three files: **PRD** (problem + scope), **ADR** (architecture decisions), **FEATURES** (Feature → Story → Task breakdown).

## Completed

| Initiative | What shipped |
|------------|-------------|
| [domain-knot-libraries/](completed/domain-knot-libraries/) | 7 domain libraries — data, agents, ml, health, signal, oilgas, connectors foundations |
| [assembler-disassembler/](completed/assembler-disassembler/) | Ingestor abolition; Assembler/Disassembler base classes; per-domain bridge knots |
| [subtapestry-contract/](completed/subtapestry-contract/) | process() returns Knot; ~90 subclass remediation; LoopSubTapestry conformance |
| [map-api-redesign/](completed/map-api-redesign/) | Map/ZipMap/DictMap as annotation markers; engine fan-out; MapTypeError guards |
| [lineage-capture/](completed/lineage-capture/) | lineage_extra() virtual method, knot source storage, explorer extra metadata + code modal |
| [who-identity/](completed/who-identity/) | RunRequest.actor/trigger, IdentityResolver chain, vcs_commit — WHO/WHY/WHICH gaps closed |

## Current

| Initiative | Status | Priority |
|------------|--------|----------|
| [lineage-gaps](current/LINEAGE_GAPS.md) | Dataset + column lineage open in backlog | — |

## Backlog

| Initiative | Status | Priority |
|------------|--------|----------|
| [dataset-lineage/](backlog/dataset-lineage/) | Not started | High — source/sink asset tracking via Assembler/Disassembler |
| [column-lineage/](backlog/column-lineage/) | Not started | Medium — tier-aware column mapping (Polars schema, Ibis/DataFusion plan walk) |
| [domain-specializations/](backlog/domain-specializations/) | Not started | High — next sprint |
| [connectors-infrastructure/](backlog/connectors-infrastructure/) | Not started | High — next sprint |
| [mutation-testing/](backlog/mutation-testing/) | Partially done (configured; CI gate pending) | Medium |
