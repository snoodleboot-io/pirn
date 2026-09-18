Processes well log and drilling data — curve validation, depth-grid normalisation, spike removal, depth and environmental corrections, petrophysical evaluation (Vsh, porosity, Sw, permeability), lithology classification, deviation surveys, well paths, and drilling engineering. Does NOT read LAS files; use `LasFormat` from `pirn.connectors.file_formats`.

## Mental model

Well log processing is a depth-indexed transform chain. Two input shapes travel through it:

- `LASPayload` (`pirn_oilgas.types.las_payload`) — the curve set carried as a payload. `LasCurveValidator` and every knot that appends a computed curve (`LogNormalizer`, `PorosityCalculator`, `WaterSaturationCalculator`, `PermeabilityEstimator`, `LithologyClassifier`, `PetrophysicalEvaluator`) takes `payload=` and returns a `LASPayload`.
- A plain `list[dict]` of samples (`depth_ft`, `raw_value`) — what the sample-level correction knots (`DepthShiftCorrector`, `EnvironmentalCorrectionApplicator`, `LogSpikeRemover`, `VshaleCalculator`) take as `log_curve=` / `gr_log=`.

Raw curves arrive with borehole-environment effects and depth uncertainty that must be removed before any petrophysical calculation is meaningful; deviation surveys convert measured depth to a 3-D well path for anything geometric.

Every knot here is imported from the module that defines it. `pirn_oilgas/well/__init__.py` re-exports nothing (`__all__` is empty) — the house convention forbids import forwarding — so importing a class straight from the `pirn_oilgas.well` package raises `ImportError`.

## Source map

```
├── casing_design_evaluator.py             CasingDesignEvaluator            — evaluates a casing design against burst, collapse, and tension limits
├── core_to_log_depth_matcher.py           CoreToLogDepthMatcher            — matches core samples to the nearest log depth within a maximum shift
├── depth_shift_corrector.py               DepthShiftCorrector              — shifts every depth in a log curve by a constant offset
├── deviation_survey_processor.py          DeviationSurveyProcessor         — validates and resamples a deviation survey to a uniform MD step
├── directional_drilling_planner.py        DirectionalDrillingPlanner       — plans a directional well to a target from the current path
├── environmental_correction_applicator.py EnvironmentalCorrectionApplicator — applies mud-weight / temperature / borehole-size corrections
├── formation_top_picker.py                FormationTopPicker               — records one formation top at a configured measured depth
├── las_curve_validator.py                 LasCurveValidator                — validates that a LASPayload contains every required curve
├── lithology_classifier.py                LithologyClassifier              — classifies lithology and appends a LITH curve
├── log_normalizer.py                      LogNormalizer                    — resamples curves onto a uniform depth grid and normalises units
├── log_spike_remover.py                   LogSpikeRemover                  — replaces spikes using a rolling MAD filter
├── mud_weight_calculator.py               MudWeightCalculator              — recommends a mud-weight window from pore / fracture pressure
├── permeability_estimator.py              PermeabilityEstimator            — estimates permeability (timur, coates, wyllie_rose)
├── petrophysical_evaluator.py             PetrophysicalEvaluator           — one interpretation pass appending VSH, PHIE, and SW curves
├── porosity_calculator.py                 PorosityCalculator               — derives a porosity curve (density, neutron, density_neutron)
├── vshale_calculator.py                   VshaleCalculator                 — Vshale from a GR log (linear, larionov, clavier)
├── water_saturation_calculator.py         WaterSaturationCalculator        — Sw from a saturation model (archie, simandoux, indonesia, waxman_smits)
├── well_path_calculator.py                WellPathCalculator               — converts a deviation survey into a 3-D well-path reference
└── witsml_drilling_monitor.py             WitsmlDrillingMonitor            — parses WITSML log data and evaluates drilling KPIs against thresholds
```

## Canonical pattern

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_oilgas.types.las_payload import LASPayload
from pirn_oilgas.well.las_curve_validator import LasCurveValidator
from pirn_oilgas.well.log_normalizer import LogNormalizer
from pirn_oilgas.well.petrophysical_evaluator import PetrophysicalEvaluator
from pirn_oilgas.well.porosity_calculator import PorosityCalculator
from pirn_oilgas.well.water_saturation_calculator import WaterSaturationCalculator

with Tapestry() as t:
    las = Parameter("las_payload", LASPayload, _config=KnotConfig(id="las_payload"))

    validated = LasCurveValidator(
        payload=las,
        required_curves=("GR", "RHOB", "RT"),
        _config=KnotConfig(id="curve_validate"),
    )

    normalised = LogNormalizer(
        payload=validated,
        target_depth_step=0.5,
        target_depth_unit="m",
        _config=KnotConfig(id="normalise"),
    )

    porosity = PorosityCalculator(
        payload=normalised,
        method="density",
        matrix_density=2.65,
        fluid_density=1.0,
        _config=KnotConfig(id="porosity"),
    )

    saturation = WaterSaturationCalculator(
        payload=porosity,
        method="archie",
        rw=0.05,
        _config=KnotConfig(id="sw"),
    )

    interpreted = PetrophysicalEvaluator(
        payload=saturation,
        _config=KnotConfig(id="petro"),
    )

result = await t.run(RunRequest(parameters={"las_payload": las_payload}))
```

Sample-level corrections work on the `list[dict]` shape instead:

```python
from pirn.core.knot_config import KnotConfig
from pirn_oilgas.well.depth_shift_corrector import DepthShiftCorrector
from pirn_oilgas.well.environmental_correction_applicator import (
    EnvironmentalCorrectionApplicator,
)
from pirn_oilgas.well.log_spike_remover import LogSpikeRemover

despiked = LogSpikeRemover(
    log_curve=raw_curve,
    window_size=11,
    mad_threshold=3.0,
    _config=KnotConfig(id="despike"),
)

shifted = DepthShiftCorrector(
    log_curve=despiked,
    shift_ft=-1.5,
    resample=True,
    _config=KnotConfig(id="depth_shift"),
)

corrected = EnvironmentalCorrectionApplicator(
    log_curve=shifted,
    correction_table={"mud_weight_ppg": 10.5, "temperature_f": 180.0},
    log_type="density",
    _config=KnotConfig(id="env_correct"),
)
```

## Anti-patterns

**Importing from the sub-package** — naming a class on the `pirn_oilgas.well` package itself (rather than on `pirn_oilgas.well.las_curve_validator`) raises `ImportError`; the `__init__.py` deliberately re-exports nothing. Import from the defining module instead.

**Mixing the two input shapes** — passing a `LASPayload`-producing knot into `log_curve=` (or a `list[dict]` into `payload=`) fails validation; convert explicitly rather than hoping the adapter coerces.

**Running `PetrophysicalEvaluator` on uncorrected curves** — it appends VSH / PHIE / SW from whatever `GR`, `RHOB` and resistivity it is given; borehole effects left in the curves propagate straight into Sw and porosity with no warning.

**Treating `LasCurveValidator` as a completeness gate** — it asserts only that every mnemonic in `required_curves` is present; it says nothing about coverage, depth range, or null fraction. Name every curve the downstream chain needs.

## Constraints and gotchas

- `LasCurveValidator` needs an explicit non-empty `required_curves` sequence — there is no default set.
- Method strings are validated and raise `ValueError` on anything else:
  - `PorosityCalculator.method` — `density`, `neutron`, `density_neutron`.
  - `WaterSaturationCalculator.method` — `archie`, `indonesia`, `simandoux`, `waxman_smits` (with `tortuosity_factor=1.0`, `cementation_exponent=2.0`, `saturation_exponent=2.0` defaults).
  - `VshaleCalculator.method` — `linear`, `larionov_older`, `larionov_tertiary`, `clavier`.
  - `PermeabilityEstimator.method` — `coates`, `timur`, `wyllie_rose`.
  - `LithologyClassifier.method` — `crossplot`, `neural_net`, `rule_based`; the payload must carry a `GR` curve.
- `PetrophysicalEvaluator` takes only `payload`; it requires a `GR` curve plus either `RHOB` or a `PHI_*` curve.
- Depth units are not interchangeable: `DepthShiftCorrector.shift_ft` and `CoreToLogDepthMatcher.max_shift_ft` are feet, while `LogNormalizer.target_depth_unit` defaults to metres.
- `WellPathCalculator.method` defaults to `minimum_curvature` and takes a `DeviationSurveyPayload`, so run `DeviationSurveyProcessor` first for a uniform MD step.
- Install extra: `pip install "pirn-oilgas[oilgas]"` (pulls `lasio`, `scipy`, `segyio`, `resfo`).

## Quick reference

| Task | How |
|------|-----|
| Assert required curves are present | `LasCurveValidator(payload=las, required_curves=("GR", "RHOB"), _config=...)` |
| Resample curves to a uniform depth grid | `LogNormalizer(payload=validated, target_depth_step=0.5, target_depth_unit="m", _config=...)` |
| Remove spikes from a sampled curve | `LogSpikeRemover(log_curve=curve, window_size=11, mad_threshold=3.0, _config=...)` |
| Correct a depth offset between runs | `DepthShiftCorrector(log_curve=curve, shift_ft=-1.5, resample=True, _config=...)` |
| Apply borehole environmental corrections | `EnvironmentalCorrectionApplicator(log_curve=curve, correction_table={...}, log_type="density", _config=...)` |
| Compute Vshale from GR | `VshaleCalculator(gr_log=curve, gr_clean=15.0, gr_shale=120.0, method="linear", _config=...)` |
| Compute porosity | `PorosityCalculator(payload=las, method="density", matrix_density=2.65, fluid_density=1.0, _config=...)` |
| Compute water saturation | `WaterSaturationCalculator(payload=las, method="archie", rw=0.05, _config=...)` |
| Estimate permeability | `PermeabilityEstimator(payload=las, method="timur", _config=...)` |
| Classify lithology | `LithologyClassifier(payload=las, method="crossplot", _config=...)` |
| Full VSH / PHIE / SW pass | `PetrophysicalEvaluator(payload=las, _config=...)` |
| Record a formation top | `FormationTopPicker(las_file=las_file, formation_name="Top_Res", depth_md=2450.0, _config=...)` |
| Depth-match core to logs | `CoreToLogDepthMatcher(core_data=core, log_data=logs, max_shift_ft=2.0, _config=...)` |
| Resample a deviation survey | `DeviationSurveyProcessor(survey=survey, target_md_step=10.0, _config=...)` |
| Build a 3-D well path | `WellPathCalculator(survey=survey, method="minimum_curvature", _config=...)` |
| Plan a directional well | `DirectionalDrillingPlanner(current_path=path, target_x=..., target_y=..., target_z=..., _config=...)` |
| Evaluate a casing design | `CasingDesignEvaluator(well_path=path, burst_limit_psi=..., collapse_limit_psi=..., tension_limit_lbf=..., _config=...)` |
| Recommend a mud-weight window | `MudWeightCalculator(drilling=drilling, pore_pressure_ppg=..., fracture_pressure_ppg=..., safety_margin_ppg=0.5, _config=...)` |
| Monitor drilling KPIs from WITSML | `WitsmlDrillingMonitor(witsml_data=data, alert_thresholds={...}, well_uid="W-1", _config=...)` |

*See also: [oilgas AGENTIC_USE.md](../AGENTIC_USE.md)*
