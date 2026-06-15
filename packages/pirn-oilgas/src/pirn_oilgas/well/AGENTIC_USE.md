Processes well log data — deviation survey, depth correction, environmental correction, petrophysical interpretation, formation top picking, and well correlation. Does NOT read LAS files; use LasFormat from file_formats.

## Mental model

Well log processing is a depth-indexed transform chain: raw curves arrive with borehole-environment effects and depth uncertainty that must be removed before any petrophysical calculation is meaningful. Deviation surveys convert measured depth to true vertical depth and x-y position, depth shift correctors align curves from different logging runs, and environmental corrections remove borehole and mud effects before lithology classification or petrophysical interpretation proceeds.

## Source map

```
├── casing_design_evaluator.py           CasingDesignEvaluator           — evaluates casing design against formation pressure and wellbore geometry
├── core_to_log_depth_matcher.py         CoreToLogDepthMatcher           — depth-matches core sample intervals to log depths
├── depth_shift_corrector.py             DepthShiftCorrector             — corrects systematic depth offsets between logging runs
├── deviation_survey_processor.py        DeviationSurveyProcessor        — computes TVD, TVT, and x-y position from MD/inclination/azimuth
├── directional_drilling_planner.py      DirectionalDrillingPlanner      — generates well path trajectories to reach a geological target
├── environmental_correction_applicator.py EnvironmentalCorrectionApplicator — applies borehole and mud filtrate corrections to raw log curves
├── formation_top_picker.py              FormationTopPicker              — picks formation tops from log signatures
├── las_curve_validator.py               LasCurveValidator               — validates curve mnemonics, units, and null-value conventions
├── lithology_classifier.py              LithologyClassifier             — classifies lithology from crossplot or neural-net model
├── log_normalization_knot.py            LogNormalizationKnot            — normalizes logs across wells using histogram or key-well method
├── petrophysical_interpreter.py         PetrophysicalInterpreter        — computes Vsh, porosity, Sw, and net-pay flags
├── synthetic_seismogram_generator.py    SyntheticSeismogramGenerator    — generates synthetic seismograms for well-to-seismic tie
├── well_correlation_builder.py          WellCorrelationBuilder          — builds cross-section correlations between multiple wells
├── well_placement_optimizer.py          WellPlacementOptimizer          — optimizes landing zone and lateral placement for reservoir contact
├── well_qc_gate.py                      WellQcGate                      — checks log completeness, depth range, and curve nulls before downstream steps
├── well_tie_processor.py                WellTieProcessor                — calibrates synthetic seismogram phase and time shift to seismic
├── zone_statistics_extractor.py         ZoneStatisticsExtractor         — computes per-zone averages for porosity, Sw, and net pay
```

## Canonical pattern

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn_oilgas.well import (
    LasCurveValidator,
    DepthShiftCorrector,
    EnvironmentalCorrectionApplicator,
    PetrophysicalInterpreter,
    WellQcGate,
)

with Tapestry() as t:
    las_curves = Parameter("las_curves", object)  # curve dict from LasFormat

    validated = LasCurveValidator(
        curves=las_curves,
        _config=KnotConfig(id="curve_validate"),
    )

    qc_passed = WellQcGate(
        curves=validated,
        _config=KnotConfig(id="well_qc"),
    )

    shifted = DepthShiftCorrector(
        curves=qc_passed,
        _config=KnotConfig(id="depth_shift", params={"reference_curve": "GR"}),
    )

    corrected = EnvironmentalCorrectionApplicator(
        curves=shifted,
        _config=KnotConfig(id="env_correct", params={"borehole_diameter_curve": "CALI"}),
    )

    petro = PetrophysicalInterpreter(
        curves=corrected,
        _config=KnotConfig(id="petro", params={"vsh_method": "larionov", "porosity_method": "density"}),
    )

result = await t.run(RunRequest(parameters={"las_curves": curve_dict}))
```

## Anti-patterns

**Running PetrophysicalInterpreter before EnvironmentalCorrectionApplicator** — uncorrected resistivity and density curves carry borehole effects that inflate or suppress Sw and porosity estimates without warning.

**Skipping DeviationSurveyProcessor for horizontal wells** — petrophysical interpretation along measured depth in a deviated well introduces significant TVD errors; always convert to TVD before zone assignments.

**Using LasCurveValidator as a gate for completeness** — the validator checks mnemonics and units but does not assert curve coverage; use WellQcGate for coverage and null-value checks.

## Constraints and gotchas

- `WellQcGate` raises `KnotCheckError` when required curves (configurable) are absent or exceed the null threshold.
- `DepthShiftCorrector` shifts all curves by the same scalar offset derived from the reference curve; multi-run depth mismatches exceeding the `max_shift_m` parameter are rejected.
- `PetrophysicalInterpreter` requires a valid `vsh_method` and at least one porosity curve; missing inputs raise `MissingCurveError` at knot initialisation.
- `SyntheticSeismogramGenerator` depends on `DeviationSurveyProcessor` output when the well is deviated; passing MD-indexed sonic without TVD conversion produces time-depth mismatches.
- Install extra: `pip install pirn[well-log]`

## Quick reference

| Task | How |
|------|-----|
| Validate curve mnemonics and units | `LasCurveValidator(curves=param)` |
| Check log completeness before processing | `WellQcGate(curves=validated)` |
| Correct depth offsets between runs | `DepthShiftCorrector(curves=qc_passed)` |
| Apply borehole environmental corrections | `EnvironmentalCorrectionApplicator(curves=shifted)` |
| Compute Vsh, porosity, and Sw | `PetrophysicalInterpreter(curves=corrected)` |
| Pick formation tops from log signatures | `FormationTopPicker(curves=petro)` |
| Compute TVD and x-y trajectory | `DeviationSurveyProcessor(survey=survey_param)` |
| Depth-match core samples to logs | `CoreToLogDepthMatcher(core=core_param, logs=log_param)` |
| Correlate formations across wells | `WellCorrelationBuilder(wells=well_list)` |
| Extract zone averages for reporting | `ZoneStatisticsExtractor(curves=petro, tops=tops)` |

*See also: [oilgas AGENTIC_USE.md](../AGENTIC_USE.md)*
