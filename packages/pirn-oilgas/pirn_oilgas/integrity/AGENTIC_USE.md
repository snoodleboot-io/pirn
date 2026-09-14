Performs asset integrity and HSE analytics — corrosion monitoring, wall-thickness assessment, inspection risk scoring, pig run analysis, PSV test record parsing, gas composition, and Scope 1 emissions reporting. Does NOT interface with inspection management systems; fetch the records upstream (e.g. with `DatabaseQuerySource`) and pass them in.

## Mental model

Asset integrity analytics is a risk-reduction pipeline: measurement knots (pig runs, wall thickness) feed the corrosion rate estimator, which feeds the risk-based inspection scorer that prioritises which assets require intervention. HSE knots (emissions, energy KPIs, gas chromatography) operate in parallel on their own inputs. All knots are stateless transforms — they do not write back to inspection management systems.

## Source map

```
├── cathodic_protection_analyzer.py      CathodicProtectionAnalyzer      — assesses CP coverage from a ScadaPayload potential series
├── corrosion_rate_estimator.py          CorrosionRateEstimator          — estimates metal-loss corrosion rate (mpy) between two pig runs
├── energy_efficiency_kpi_calculator.py  EnergyEfficiencyKpiCalculator   — computes energy / production efficiency KPIs from two ScadaPayloads
├── gas_chromatography_analyzer.py       GasChromatographyAnalyzer       — computes component mole fractions and heating value from a GC report
├── pig_run_data_processor.py            PigRunDataProcessor             — processes an inline-inspection pig run into a feature-table summary
├── psv_test_record_parser.py            PSVTestRecordParser             — parses a pressure safety valve test record and checks required fields
├── risk_based_inspection_scorer.py      RiskBasedInspectionScorer       — scores an asset as probability of failure x consequence (API RP 580/581)
├── scope1_emissions_reporter.py         Scope1EmissionsReporter         — aggregates Scope 1 GHG emissions from flaring, venting, and combustion events
├── wall_thickness_analyzer.py           WallThicknessAnalyzer           — assesses remaining wall thickness against the minimum allowable
```

## Canonical pattern

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_oilgas.integrity.corrosion_rate_estimator import CorrosionRateEstimator
from pirn_oilgas.integrity.pig_run_data_processor import PigRunDataProcessor
from pirn_oilgas.integrity.risk_based_inspection_scorer import RiskBasedInspectionScorer
from pirn_oilgas.integrity.wall_thickness_analyzer import WallThicknessAnalyzer

with Tapestry() as t:
    previous_path = Parameter("previous_run_path", str)
    current_path = Parameter("current_run_path", str)

    previous_run = PigRunDataProcessor(
        pipeline_id="PL-7",
        run_path=previous_path,
        _config=KnotConfig(id="pig_previous"),
    )
    current_run = PigRunDataProcessor(
        pipeline_id="PL-7",
        run_path=current_path,
        _config=KnotConfig(id="pig_current"),
    )

    wall = WallThicknessAnalyzer(
        pig_run=current_run,
        nominal_thickness_in=0.500,
        minimum_allowable_thickness_in=0.300,
        _config=KnotConfig(id="wall_thickness"),
    )

    corrosion = CorrosionRateEstimator(
        previous_run=previous_run,
        current_run=current_run,
        years_between=3.0,
        _config=KnotConfig(id="corrosion_rate"),
    )

    rbi = RiskBasedInspectionScorer(
        corrosion_assessment=corrosion,
        consequence_score=0.7,
        _config=KnotConfig(id="rbi"),
    )

result = await t.run(
    RunRequest(parameters={"previous_run_path": "ili/2023.csv", "current_run_path": "ili/2026.csv"})
)
```

## Anti-patterns

**Running RiskBasedInspectionScorer on raw pig-run output** — the scorer derives probability of failure from `max_rate_mpy` in its `corrosion_assessment` input; a dict without that key scores as a zero corrosion rate, silently understating risk. Feed it `CorrosionRateEstimator` output.

**Relying on Scope1EmissionsReporter default factors for unlisted gases** — with `co2_eq_factors=None` the reporter uses `{"ch4": 25.0, "n2o": 298.0, "co2": 1.0}`, and any event `gas_type` missing from the factor dict is weighted 1.0. Pass explicit factors covering every gas type your events carry.

## Constraints and gotchas

- `CorrosionRateEstimator` requires `years_between > 0` and a `feature_count` field in `current_run`; otherwise it raises `ValueError`.
- `RiskBasedInspectionScorer` requires `consequence_score` in [0, 1]; out-of-range values raise `ValueError`.
- `WallThicknessAnalyzer` raises `ValueError` unless both thicknesses are positive and `minimum_allowable_thickness_in < nominal_thickness_in`.
- `PSVTestRecordParser` raises `ValueError` naming any of `required_fields` (default `tag`, `set_pressure_psi`, `test_date`, `pass_fail`) missing from the record.
- `CathodicProtectionAnalyzer` and `EnergyEfficiencyKpiCalculator` accept only `ScadaPayload` inputs (e.g. from `ScadaDatabaseAssembler`); anything else raises `TypeError`.
- Install extra: `pip install "pirn-oilgas[oilgas]"`

## Quick reference

| Task | How |
|------|-----|
| Process an ILI pig run | `PigRunDataProcessor(pipeline_id=..., run_path=...)` |
| Assess remaining wall thickness | `WallThicknessAnalyzer(pig_run=..., nominal_thickness_in=..., minimum_allowable_thickness_in=...)` |
| Compute corrosion rate (mpy) | `CorrosionRateEstimator(previous_run=..., current_run=..., years_between=...)` |
| Score assets for inspection priority | `RiskBasedInspectionScorer(corrosion_assessment=..., consequence_score=...)` |
| Evaluate cathodic protection coverage | `CathodicProtectionAnalyzer(potential_series=..., protection_threshold_mv=...)` |
| Parse a PSV test record | `PSVTestRecordParser(raw_record=...)` |
| Process GC compositional analysis | `GasChromatographyAnalyzer(gc_report=...)` |
| Report Scope 1 GHG emissions | `Scope1EmissionsReporter(events=..., co2_eq_factors=...)` |
| Calculate facility energy KPIs | `EnergyEfficiencyKpiCalculator(energy_consumption=..., production=...)` |

*See also: [oilgas AGENTIC_USE.md](../AGENTIC_USE.md)*
