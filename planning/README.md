# Planning

This directory tracks all product and architectural decisions for pirn.

## Structure

```
planning/
  completed/    Work that shipped. PRDs, ADRs, and delivery stories.
  backlog/      Work that has not yet started. PRDs and story breakdowns.
```

## Completed

| Document | What it records |
|----------|----------------|
| [PRD-domain-knot-libraries.md](completed/PRD-domain-knot-libraries.md) | Full scope of the domain knot library initiative — 7 domains, what shipped |
| [ADR-001-assembler-disassembler.md](completed/ADR-001-assembler-disassembler.md) | Decision to delete ingestors and introduce Assembler/Disassembler base classes |
| [ADR-002-subtapestry-contract.md](completed/ADR-002-subtapestry-contract.md) | `SubTapestry.process()` returns a `Knot`; base class owns inner run |
| [ADR-003-map-annotation-api.md](completed/ADR-003-map-annotation-api.md) | Map/ZipMap/DictMap as input-annotation markers, not wrapper knots |
| [ADR-004-payload-generic-base.md](completed/ADR-004-payload-generic-base.md) | `Payload[M, D]` generic base class for all domain payloads |
| [STORIES.md](completed/STORIES.md) | Stories → features → tasks for all delivered work |
| [assembler-disassembler-plan.md](completed/assembler-disassembler-plan.md) | Original 5-phase execution plan for the assembler refactor |
| [security-analysis.md](completed/security-analysis.md) | 14-finding security audit + remediation status (all complete) |

## Backlog

| Document | What it covers |
|----------|---------------|
| [PRD-domain-knot-specializations.md](backlog/PRD-domain-knot-specializations.md) | ~127 unimplemented specializations across data, agents, ml, health, signal, oilgas |
| [STORIES-domain-specializations.md](backlog/STORIES-domain-specializations.md) | Per-domain stories with named missing classes |
| [PRD-connectors-infrastructure.md](backlog/PRD-connectors-infrastructure.md) | 48-class connectors subsystem — Postgres, S3, Kafka, BigQuery, Snowflake, etc. |
| [PRD-mutation-testing.md](backlog/PRD-mutation-testing.md) | Mutation testing CI integration (mutmut configured; gate not yet wired) |

## Format conventions

**PRD** — Problem statement, goals, scope, success criteria. One per initiative.

**ADR** — Architecture Decision Record. Context, decision, alternatives, consequences. Immutable once accepted.

**STORIES** — `As a / I want / So that` stories, broken into Features and Tasks. Stories represent user-visible value; features are discrete deliverables; tasks are individual code changes.
