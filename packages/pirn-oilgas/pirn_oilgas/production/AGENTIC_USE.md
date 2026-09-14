Analyzes production data — rate validation and normalisation, GOR and water cut, decline rate and forecasting, artificial lift optimisation, ESP health monitoring, well tests, tank gauging, and flaring measurement. Does NOT interface with SCADA or historian systems; fetch historian rows upstream (e.g. with `DatabaseQuerySource`) and assemble them with `ScadaDatabaseAssembler`.

## Mental model

Production analytics operates on time-series streams of rate, pressure, and equipment state. Most series-based knots here consume a `ScadaPayload` produced by `ScadaDatabaseAssembler`; validation knots bound-check the series, derived-quantity knots (GOR, water cut, injection) combine series, and decline knots estimate a trend that `ProductionForecaster` projects forward. A second group of record-based knots (ESP health, gas lift, rod pump, separator tests, tank gauging, flaring) take plain dicts. All knots treat the incoming data as already-ingested — SCADA connectivity is out of scope. Allocation of field volumes to wells lives in the reservoir sub-package (`ProductionAllocationEngine`).

## Source map

```
├── artificial_lift_optimizer.py      ArtificialLiftOptimizer      — recommends a lift-system operating point for a production ScadaPayload
├── decline_rate_estimator.py         DeclineRateEstimator         — short-window fractional annual decline rate from a rate series
├── downtime_event_classifier.py      DowntimeEventClassifier      — classifies downtime events from gaps in a production series
├── esp_health_monitor.py             EspHealthMonitor             — scores ESP telemetry against vibration and temperature thresholds
├── flaring_measurement_processor.py  FlaringMeasurementProcessor  — computes total gas flared and emissions from flare measurements
├── flowline_pressure_modeler.py      FlowlinePressureModeler      — predicts flowline pressure drop from a rate series
├── gas_lift_optimizer.py             GasLiftOptimizer             — optimises gas injection rate against a well performance curve
├── gas_oil_ratio_calculator.py       GasOilRatioCalculator        — computes GOR from oil- and gas-rate series
├── production_forecaster.py          ProductionForecaster         — projects a future rate series from Arps decline parameters
├── production_rate_normalizer.py     ProductionRateNormalizer     — normalises measured rates to reference pressure and temperature
├── production_test_validator.py      ProductionTestValidator      — checks a production-test series against oil, gas, and water rate bounds
├── rod_pump_optimizer.py             RodPumpOptimizer             — optimises rod pump stroke speed from a dynagraph card
├── separator_test_processor.py       SeparatorTestProcessor       — computes GOR, WOR, and shrinkage from separator test data
├── tank_gauging_processor.py         TankGaugingProcessor         — computes net oil volume and BS&W from tank gauge readings
├── water_cut_tracker.py              WaterCutTracker              — derives a water-cut series from oil and water rates
├── water_injection_tracker.py        WaterInjectionTracker        — tracks injected water volumes from an injection-rate series
├── well_test_analyzer.py             WellTestAnalyzer             — extracts permeability and skin from a well-test pressure series
```

## Canonical pattern

```python
from datetime import UTC, datetime

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_oilgas.assemblers.scada_database_assembler import ScadaDatabaseAssembler
from pirn_oilgas.production.decline_rate_estimator import DeclineRateEstimator
from pirn_oilgas.production.production_forecaster import ProductionForecaster
from pirn_oilgas.production.production_test_validator import ProductionTestValidator
from pirn_oilgas.production.water_cut_tracker import WaterCutTracker
from pirn_oilgas.reservoir.decline_curve_analyzer import DeclineCurveAnalyzer

since = datetime(2026, 1, 1, tzinfo=UTC)

with Tapestry() as t:
    oil_rows = Parameter("oil_rows", list)      # historian rows from DatabaseQuerySource
    water_rows = Parameter("water_rows", list)

    oil = ScadaDatabaseAssembler(
        rows=oil_rows, tag="WELL-12.OIL", since=since, sample_interval_sec=86400.0,
        _config=KnotConfig(id="oil_series"),
    )
    water = ScadaDatabaseAssembler(
        rows=water_rows, tag="WELL-12.WATER", since=since, sample_interval_sec=86400.0,
        _config=KnotConfig(id="water_series"),
    )

    validated = ProductionTestValidator(
        series=oil,
        max_oil_rate_bopd=5000.0,
        max_gas_rate_mscfd=20000.0,
        max_water_rate_bwpd=8000.0,
        _config=KnotConfig(id="validate"),
    )

    water_cut = WaterCutTracker(oil_rate=validated, water_rate=water, _config=KnotConfig(id="water_cut"))
    decline_rate = DeclineRateEstimator(rate_series=validated, window_days=90, _config=KnotConfig(id="decline_rate"))

    arps = DeclineCurveAnalyzer(rate_series=validated, method="hyperbolic", _config=KnotConfig(id="arps"))
    forecast = ProductionForecaster(decline_parameters=arps, forecast_months=24, _config=KnotConfig(id="forecast"))

result = await t.run(RunRequest(parameters={"oil_rows": oil_row_list, "water_rows": water_row_list}))
```

## Anti-patterns

**Passing raw historian rows to series knots** — `GasOilRatioCalculator`, `WaterCutTracker`, `DeclineRateEstimator`, `ArtificialLiftOptimizer`, and the other series knots raise `TypeError` unless their input is a `ScadaPayload`; assemble rows with `ScadaDatabaseAssembler` first.

**Feeding DeclineRateEstimator output to ProductionForecaster** — `DeclineRateEstimator` returns a single fractional annual rate, while `ProductionForecaster` requires a dict with `qi`, `di_per_year`, and `b` (a missing key raises `KeyError`). Use `DeclineCurveAnalyzer` from the reservoir sub-package for the forecaster's input.

**Running GasLiftOptimizer and ArtificialLiftOptimizer on the same wells in one run** — both emit operating-point recommendations and will produce conflicting outputs; choose one optimiser per well group.

## Constraints and gotchas

- `ProductionTestValidator` requires all three rate bounds to be positive numbers and returns the series unchanged when it passes.
- `DeclineRateEstimator` requires `window_days` to be a positive `int`.
- `ArtificialLiftOptimizer` accepts `lift_type` in `esp`, `gas_lift`, `rod_pump`, `pcp`, `jet_pump`; `WellTestAnalyzer` accepts `method` in `horner`, `mdh`, `deconvolution`.
- `EspHealthMonitor`, `FlaringMeasurementProcessor`, `GasLiftOptimizer`, `RodPumpOptimizer`, `SeparatorTestProcessor`, `TankGaugingProcessor`, and `WellTestAnalyzer` declare their inputs only through `process()`; pass those parameter names as keyword inputs (for example `EspHealthMonitor(telemetry=..., vibration_threshold_g=..., temperature_threshold_c=..., _config=...)`).
- `EspHealthMonitor` requires `motor_temp_c` and `vibration_g` in the telemetry dict; `FlaringMeasurementProcessor` requires `efficiency_factor` in (0, 1].
- Install extra: `pip install "pirn-oilgas[oilgas]"`

## Quick reference

| Task | How |
|------|-----|
| Assemble historian rows into a series | `ScadaDatabaseAssembler(rows=..., tag=..., since=..., sample_interval_sec=...)` |
| Bound-check a production test | `ProductionTestValidator(series=..., max_oil_rate_bopd=..., max_gas_rate_mscfd=..., max_water_rate_bwpd=...)` |
| Normalise rates to standard conditions | `ProductionRateNormalizer(measurements=..., reference_pressure_psia=..., reference_temp_f=...)` |
| Compute GOR | `GasOilRatioCalculator(oil_rate=..., gas_rate=...)` |
| Track water cut | `WaterCutTracker(oil_rate=..., water_rate=...)` |
| Track water injection | `WaterInjectionTracker(injection_rate=...)` |
| Estimate short-window decline rate | `DeclineRateEstimator(rate_series=..., window_days=...)` |
| Forecast production | `ProductionForecaster(decline_parameters=..., forecast_months=...)` |
| Model flowline pressure drop | `FlowlinePressureModeler(rate_series=..., pipe_inner_diameter_in=..., pipe_length_ft=...)` |
| Recommend a lift operating point | `ArtificialLiftOptimizer(production=..., lift_type=...)` |
| Monitor ESP health | `EspHealthMonitor(telemetry=..., vibration_threshold_g=..., temperature_threshold_c=...)` |
| Classify downtime events | `DowntimeEventClassifier(production_series=..., gap_threshold_hours=...)` |
| Process flare meter data | `FlaringMeasurementProcessor(measurements=..., gas_composition=..., efficiency_factor=...)` |
| Analyse a well test | `WellTestAnalyzer(pressure_series=..., method=...)` |

*See also: [oilgas AGENTIC_USE.md](../AGENTIC_USE.md)*
