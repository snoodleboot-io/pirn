Analyzes production data — allocation, decline curve analysis, artificial lift optimization, ESP health monitoring, and flaring measurement. Does NOT interface with SCADA or historian systems; ingest production data via DatabaseQuerySource.

## Mental model

Production analytics operates on time-series streams of rate, pressure, and equipment state. Allocation distributes measured facility volumes back to individual wells; decline analysis fits production trends to forecast reserves; artificial lift knots optimize injection rate or pump settings against a cost or production objective. All knots treat the incoming data as already-ingested frames — SCADA connectivity is out of scope.

## Source map

```
├── artificial_lift_optimizer.py      ArtificialLiftOptimizer      — optimizes gas-lift injection rate or ESP frequency for target production
├── decline_rate_estimator.py         DeclineRateEstimator         — fits Arps decline parameters (qi, Di, b) to production history
├── downtime_event_classifier.py      DowntimeEventClassifier      — classifies production downtime events from rate anomalies and remarks
├── esp_health_monitor.py             EspHealthMonitor             — monitors ESP current, vibration, and temperature for failure precursors
├── flaring_measurement_processor.py  FlaringMeasurementProcessor  — processes flare meter readings into reportable flared volumes
├── flowline_pressure_modeler.py      FlowlinePressureModeler      — models flowing pressure along a flowline network
├── gas_lift_optimizer.py             GasLiftOptimizer             — optimizes gas-lift allocation across a well group
├── gas_oil_ratio_calculator.py       GasOilRatioCalculator        — computes GOR from measured gas and oil production rates
├── injection_efficiency_analyzer.py  InjectionEfficiencyAnalyzer  — evaluates water/gas injection efficiency against voidage replacement
├── production_allocation_engine.py   ProductionAllocationEngine   — allocates facility-level volumes to individual wells
├── production_data_qc_gate.py        ProductionDataQcGate         — validates production time series for nulls, spikes, and date gaps
├── rate_transient_analyzer.py        RateTransientAnalyzer        — performs rate-transient analysis for reservoir characterization
├── voidage_replacement_calculator.py VoidageReplacementCalculator — calculates voidage replacement ratio for waterflood management
├── water_cut_predictor.py            WaterCutPredictor            — forecasts water cut evolution using decline or ML models
├── well_performance_benchmarker.py   WellPerformanceBenchmarker   — benchmarks individual well performance against peer or IPR curve
```

## Canonical pattern

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn.domains.oilgas.production import (
    ProductionDataQcGate,
    ProductionAllocationEngine,
    DeclineRateEstimator,
    EspHealthMonitor,
)

with Tapestry() as t:
    production_ts = Parameter("production_ts", object)  # DataFrame from DatabaseQuerySource

    qc_passed = ProductionDataQcGate(
        timeseries=production_ts,
        _config=KnotConfig(id="prod_qc"),
    )

    allocated = ProductionAllocationEngine(
        facility_volumes=qc_passed,
        _config=KnotConfig(id="allocate", params={"method": "proportional"}),
    )

    decline = DeclineRateEstimator(
        well_rates=allocated,
        _config=KnotConfig(id="decline", params={"model": "hyperbolic"}),
    )

    esp_health = EspHealthMonitor(
        esp_telemetry=qc_passed,
        _config=KnotConfig(id="esp_health", params={"vibration_threshold": 0.15}),
    )

result = await t.run(RunRequest(parameters={"production_ts": df}))
```

## Anti-patterns

**Passing raw SCADA exports directly to DeclineRateEstimator** — SCADA data contains equipment downtime zeroes that distort decline fits; always pass through ProductionDataQcGate and ProductionAllocationEngine first.

**Running GasLiftOptimizer and ArtificialLiftOptimizer on the same wells in parallel** — both knots emit injection rate recommendations and will produce conflicting outputs; choose one optimizer per well group per run.

**Using DeclineRateEstimator on fewer than 6 months of stable production** — Arps fitting on ramp-up data yields unreliable Di and b parameters that overestimate EUR; filter to plateau or declining periods before fitting.

## Constraints and gotchas

- `ProductionDataQcGate` raises `KnotCheckError` on date gaps exceeding `max_gap_days` (default 3); set explicitly for wells with planned shutdowns.
- `ProductionAllocationEngine` requires facility-level oil, gas, and water totals and a well-count or test-rate basis; missing totals raise `AllocationBasisError`.
- `DeclineRateEstimator` with `model="hyperbolic"` clips b to [0, 2]; values outside that range indicate non-decline data and are logged as warnings.
- `EspHealthMonitor` expects 1-minute or finer telemetry; coarser intervals suppress vibration anomaly detection.
- Install extra: `pip install pirn[oilgas]`

## Quick reference

| Task | How |
|------|-----|
| Validate production time series | `ProductionDataQcGate(timeseries=param)` |
| Allocate facility volumes to wells | `ProductionAllocationEngine(facility_volumes=qc_passed)` |
| Fit Arps decline parameters | `DeclineRateEstimator(well_rates=allocated)` |
| Monitor ESP health indicators | `EspHealthMonitor(esp_telemetry=ts)` |
| Optimize gas-lift injection | `GasLiftOptimizer(well_rates=allocated)` |
| Compute voidage replacement ratio | `VoidageReplacementCalculator(injection=inj, production=prod)` |
| Forecast water cut | `WaterCutPredictor(well_rates=allocated)` |
| Classify downtime events | `DowntimeEventClassifier(timeseries=qc_passed)` |
| Benchmark well against peers | `WellPerformanceBenchmarker(well_rates=allocated)` |
| Process flare meter data | `FlaringMeasurementProcessor(flare_ts=param)` |

*See also: [oilgas AGENTIC_USE.md](../AGENTIC_USE.md)*
