# Planning

Each initiative has three files: **PRD** (problem + scope), **ADR** (architecture decisions), **FEATURES** (Feature → Story → Task breakdown).

## Completed

| Initiative | What shipped |
|------------|-------------|
| [domain-knot-libraries/](completed/domain-knot-libraries/) | 7 domain libraries — data, agents, ml, health, signal, oilgas, connectors foundations |
| [assembler-disassembler/](completed/assembler-disassembler/) | Ingestor abolition; Assembler/Disassembler base classes; per-domain bridge knots |
| [subtapestry-contract/](completed/subtapestry-contract/) | process() returns Knot; ~90 subclass remediation; LoopSubTapestry conformance |
| [map-api-redesign/](completed/map-api-redesign/) | Map/ZipMap/DictMap as annotation markers; engine fan-out; MapTypeError guards |

## Backlog

| Initiative | Status | Priority |
|------------|--------|----------|
| [domain-specializations/](backlog/domain-specializations/) | Not started | High — next sprint |
| [connectors-infrastructure/](backlog/connectors-infrastructure/) | Not started | High — next sprint |
| [mutation-testing/](backlog/mutation-testing/) | Partially done (configured; CI gate pending) | Medium |
