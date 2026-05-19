# ADR: Domain Knot Specializations

**Status:** TBD — to be written when sprint starts
**Initiative:** domain-specializations
**Depends on:** ADR from domain-knot-libraries (Payload[M,D], assembler/disassembler, single-package)

---

## Context

These specializations build on the domain knot library foundation from `feat/domain-gap-remediation-plan`. All core patterns (Payload[M, D], assembler/disassembler, SubTapestry contract, optional-extras packaging) are established. The decisions in this initiative are narrower — they concern how to compose existing knots into higher-order patterns and whether certain specializations should be Knots or SubTapestries.

Key constraints inherited from the domain-knot-libraries ADR:
- All code ships in `pirn/domains/` under optional extras
- SubTapestry specializations must conform to the `_run_inner()` contract
- No ingestor knots; all I/O goes through connector knots composed with assemblers/disassemblers
- Payload[M, D] is the required type at all domain boundaries

---

## Open Architectural Questions

These must be resolved before implementation begins.

**1. Should SCD knots be SubTapestry or Knot?**

SCD Type 2 (`SCDType2`) requires reading the current dimension state, computing deltas, and writing both a close record and an open record — a multi-step operation. The question is whether this logic belongs in a single `Knot.process()` (which keeps the unit small but hides the internal steps from the run history) or in a `SubTapestry` (which exposes each step as a separate run, but adds nesting overhead). SCD Types 1 and 3 are simpler and may belong as plain Knots.

**2. Should the CDC knot own consumer lifecycle or delegate to a Source?**

`CdcDebezium` currently consumes from a message broker internally. The question is whether to refactor it as a `Source` that yields change events (keeping the knot boundary at the connector level) or keep it as a self-contained `Knot` that manages its own consumer lifecycle. The Source pattern is more composable but requires the broker configuration to be passed through the pipeline rather than held by the knot.

**3. Should the OMOP CDM mapper ship with a bundled in-memory vocabulary fixture?**

The OMOP mapper is blocked on vocabulary data. One option: ship a minimal vocabulary fixture (concept IDs for a small test domain) as a package data file, using it for both unit tests and a "no-vocabulary-DB" smoke-test mode. The alternative is to require the user to supply the vocabulary DB and mark all OMOP tests as `@pytest.mark.slow` + `@pytest.mark.requires_omop_db`. The fixture approach unblocks the implementation but risks giving users a false sense of production readiness.

**4. Should cross-tier bridge knots use Polars' native `from_arrow()` / `to_arrow()` or go through DataBatch as an intermediate?**

The two common bridges are `DataBatchToPolars` and `PolarsToArrow`. Using Polars' native `from_arrow()` is faster and zero-copy for compatible schemas, but bypasses the `DataBatch` schema metadata. Going through `DataBatch` preserves schema provenance but adds a copy. The decision affects whether the bridge knots can preserve lineage metadata across the tier boundary.

---

## Decision

TBD — document decisions here when the sprint is planned.

---

## Consequences

TBD.
