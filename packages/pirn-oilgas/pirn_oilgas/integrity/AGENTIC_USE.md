Performs asset integrity and HSE analytics — corrosion monitoring, inspection risk scoring, pig run analysis, PSV test record parsing, and Scope 1 emissions reporting. Does NOT interface with inspection management systems; ingest data via DatabaseQuerySource.

## Mental model

Asset integrity analytics is a risk-reduction pipeline: measurement knots (pig runs, wall thickness, corrosion coupons) feed rate estimators, which feed risk-based inspection scorers that prioritise which assets require intervention. HSE knots (emissions, energy KPIs) operate in parallel on the same source data. All knots are stateless transforms — they do not write back to inspection management systems.

## Source map

```
├── cathodic_protection_analyzer.py      CathodicProtectionAnalyzer      — evaluates CP system effectiveness from survey potential readings
├── corrosion_rate_estimator.py          CorrosionRateEstimator          — estimates corrosion rate (mm/yr) from wall thickness or coupon data
├── energy_efficiency_kpi_calculator.py  EnergyEfficiencyKpiCalculator   — computes energy intensity and efficiency KPIs for facilities
├── gas_chromatography_analyzer.py       GasChromatographyAnalyzer       — processes GC compositional analysis results
├── pig_run_data_processor.py            PigRunDataProcessor             — processes inline inspection pig run data into anomaly records
├── psv_test_record_parser.py            PsvTestRecordParser             — parses PSV test records to check set-pressure compliance
├── risk_based_inspection_scorer.py      RiskBasedInspectionScorer       — scores assets using API 581 or custom RBI methodology
├── scope1_emissions_reporter.py         Scope1EmissionsReporter         — calculates and formats Scope 1 GHG emissions for regulatory reporting
├── wall_thickness_loss_estimator.py     WallThicknessLossEstimator      — estimates wall thickness loss rate from UT or MFL inspection data
```

## Canonical pattern

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn_oilgas.integrity import (
    PigRunDataProcessor,
    WallThicknessLossEstimator,
    CorrosionRateEstimator,
    RiskBasedInspectionScorer,
)

with Tapestry() as t:
    pig_data = Parameter("pig_data", object)   # DataFrame from DatabaseQuerySource

    anomalies = PigRunDataProcessor(
        pig_run=pig_data,
        _config=KnotConfig(id="pig_process", params={"tool_type": "mfl"}),
    )

    thickness_loss = WallThicknessLossEstimator(
        anomalies=anomalies,
        _config=KnotConfig(id="wt_loss"),
    )

    corrosion_rate = CorrosionRateEstimator(
        thickness_history=thickness_loss,
        _config=KnotConfig(id="corr_rate", params={"method": "linear"}),
    )

    rbi_score = RiskBasedInspectionScorer(
        corrosion_rate=corrosion_rate,
        _config=KnotConfig(id="rbi", params={"methodology": "api_581"}),
    )

result = await t.run(RunRequest(parameters={"pig_data": df}))
```

## Anti-patterns

**Running RiskBasedInspectionScorer without upstream CorrosionRateEstimator** — passing raw thickness readings without a computed rate causes the scorer to fall back to default corrosion assumptions, silently understating risk for active corrosion loops.

**Using Scope1EmissionsReporter before GasChromatographyAnalyzer** — emissions factors depend on gas composition; using default methane-only factors when compositional data is available produces non-compliant regulatory reports.

**Passing coupon data directly to WallThicknessLossEstimator** — the estimator expects inspection-tool UT or MFL data; coupon data must first go through CorrosionRateEstimator directly, bypassing the thickness estimator.

## Constraints and gotchas

- `RiskBasedInspectionScorer` with `methodology="api_581"` requires fluid toxicity and flammability inputs; missing fields raise `RbiInputError`.
- `PigRunDataProcessor` validates that clock-distance alignment is within 0.5% of nominal pipe length; misaligned runs are rejected with `PigAlignmentError`.
- `Scope1EmissionsReporter` uses GWP-100 factors from the configured IPCC assessment report version; changing the version between runs produces non-comparable outputs — pin it in `_config.params`.
- `PsvTestRecordParser` flags PSVs where measured set pressure deviates more than ±3% from nameplate; these are emitted as `ComplianceFlag` records, not errors.
- Install extra: `pip install pirn[oilgas]`

## Quick reference

| Task | How |
|------|-----|
| Process MFL or UT pig run data | `PigRunDataProcessor(pig_run=param)` |
| Estimate wall thickness loss rate | `WallThicknessLossEstimator(anomalies=pig_output)` |
| Compute corrosion rate (mm/yr) | `CorrosionRateEstimator(thickness_history=wt_loss)` |
| Score assets for inspection priority | `RiskBasedInspectionScorer(corrosion_rate=rate)` |
| Evaluate cathodic protection survey | `CathodicProtectionAnalyzer(cp_survey=param)` |
| Parse PSV test records for compliance | `PsvTestRecordParser(test_records=param)` |
| Process GC compositional analysis | `GasChromatographyAnalyzer(gc_data=param)` |
| Report Scope 1 GHG emissions | `Scope1EmissionsReporter(production_data=param, gc=gc_output)` |
| Calculate facility energy KPIs | `EnergyEfficiencyKpiCalculator(energy_data=param)` |

*See also: [oilgas AGENTIC_USE.md](../AGENTIC_USE.md)*
