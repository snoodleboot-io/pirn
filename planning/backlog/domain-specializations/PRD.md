# PRD: Domain Knot Specializations

**Status:** Backlog
**Initiative:** domain-specializations
**Depends on:** domain-knot-libraries (complete)

---

## Problem

The domain-knot-libraries initiative shipped the first layer of every domain: core types, assemblers/disassemblers, base knots, and straightforward specializations. What remains is the second layer — higher-order SubTapestry compositions, domain workflow pipelines, and operational patterns that sit above individual knots but below full user pipelines.

These missing specializations are the patterns practitioners reach for most in production:

- **Data:** Cross-tier bridge knots are absent. Engineers bridging Polars and PyArrow frames, or DataBatch and Polars, must write their own conversion glue.
- **Agents:** No domain-specific agent workflow SubTapestries for code generation, document Q&A, or data analysis agent tasks. The current specializations cover ReAct/RAG mechanics but not end-to-end task pipelines.
- **ML:** The `feature_store_reader` and `feature_store_writer` specializations depend on `feature_store_provider.py`, which is abstract. No concrete implementation ships with pirn, so those two knots are unreachable in practice without user-supplied wiring.
- **Health:** The OMOP CDM mapper is blocked on a vocabulary database requirement and was intentionally deferred. No OMOP target mapping pipeline exists. Lab instrument integration (`LabInstrumentConnection`) has no concrete connector-side implementation.
- **Signal:** Frequency-domain specializations for communication systems (OFDM, matched filter) are absent. The statistical estimators (`ARModelEstimator`, `EspritEstimator`, `MUSICEstimator`, `PisarenkoEstimator`) have no composed workflow that sequences them for real-world signal classification tasks.
- **OilGas:** The four workflow SubTapestries (`SeismicToWellTieWorkflow`, `WellborePetrophysicsWorkflow`, `DeclineCurveReservesWorkflow`, `FieldProductionReportingWorkflow`) exist but lack the corresponding reporting, export, and handoff knots that make them usable end-to-end.

## Goal

Deliver the missing second-layer specializations that close the gap between "I have knots" and "I can compose a production-grade pipeline."

## Success Criteria

- Cross-tier bridge knots exist for the two most common transitions (DataBatch ↔ Polars, Polars ↔ PyArrow)
- At least three domain-specific agent task pipelines ship (code generation, document Q&A, data analysis)
- ML `FeatureStoreReader` and `FeatureStoreWriter` have at least one concrete in-process feature store implementation
- Health OMOP mapper ships with a bundled vocabulary fixture for testing; production deployments supply the real vocabulary DB
- All four oilgas workflow SubTapestries have complete export and reporting tails
- Signal communication-domain specializations cover OFDM demodulation and matched filter detection

## Out of Scope

- New connector backends (tracked separately under connectors-infrastructure)
- Per-element lineage for Map-distributed knots (tracked separately; requires engine changes)
- New domain libraries beyond the seven shipped (future initiative)
