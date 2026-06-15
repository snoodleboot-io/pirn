Performs reservoir engineering calculations — material balance, PVT processing, decline curve analysis, Monte Carlo uncertainty quantification, and simulation result parsing. Does NOT run reservoir simulators; it processes their output files (CMG, Eclipse SMSPEC).

## Mental model

Reservoir engineering in pirn is a calculation layer that sits downstream of simulator output and upstream of decision-support reports. Simulation parsers ingest binary or ASCII output files and emit structured tables; calculation knots (material balance, STOIIP, recovery factor) operate on those tables along with PVT and production data; uncertainty knots wrap any calculation in a Monte Carlo ensemble to propagate parameter uncertainty into reserve distributions.

## Source map

```
├── cmg_ssfile_parser.py               CmgSsfileParser               — parses CMG Results binary SS files into time-series tables
├── decline_curve_analyzer.py          DeclineCurveAnalyzer          — fits and forecasts Arps or stretched-exponential decline curves
├── eclipse_smspec_parser.py           EclipseSmspecParser           — parses Eclipse SMSPEC/UNSMRY summary output into DataFrames
├── material_balance_calculator.py     MaterialBalanceCalculator     — applies Havlena-Odeh or Dake material balance to reservoir data
├── monte_carlo_simulator.py           MonteCarloSimulator           — runs Monte Carlo sampling over parameterised calculation knots
├── pressure_transient_analyzer.py     PressureTransientAnalyzer     — interprets buildup and drawdown tests for permeability and skin
├── production_allocation_engine.py    ProductionAllocationEngine    — allocates simulation-sector volumes to individual well streams
├── pvt_table_processor.py             PvtTableProcessor             — validates and interpolates PVT tables (Bo, Rs, viscosity vs. pressure)
├── recovery_factor_estimator.py       RecoveryFactorEstimator       — estimates recovery factor from material balance or analogue statistics
├── reservoir_quality_indexer.py       ReservoirQualityIndexer       — computes reservoir quality index (RQI) and flow zone indicator (FZI)
├── simulation_result_comparator.py    SimulationResultComparator    — compares two simulation runs on key summary vectors
├── stoiip_calculator.py               StoiipCalculator              — calculates STOIIP and GIIP from volumetric or material balance inputs
├── uncertainty_quantifier.py          UncertaintyQuantifier         — aggregates Monte Carlo output into P10/P50/P90 reserve distributions
```

## Canonical pattern

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn_oilgas.reservoir import (
    EclipseSmspecParser,
    PvtTableProcessor,
    DeclineCurveAnalyzer,
    MaterialBalanceCalculator,
    UncertaintyQuantifier,
    MonteCarloSimulator,
)

with Tapestry() as t:
    smspec_bytes = Parameter("smspec_bytes", bytes)   # raw SMSPEC from FileSource
    pvt_table    = Parameter("pvt_table", object)     # PVT DataFrame

    sim_summary = EclipseSmspecParser(
        smspec=smspec_bytes,
        _config=KnotConfig(id="parse_smspec"),
    )

    pvt = PvtTableProcessor(
        pvt=pvt_table,
        _config=KnotConfig(id="pvt_process"),
    )

    decline = DeclineCurveAnalyzer(
        production=sim_summary,
        _config=KnotConfig(id="decline", params={"model": "arps_hyperbolic"}),
    )

    material_balance = MaterialBalanceCalculator(
        production=sim_summary,
        pvt=pvt,
        _config=KnotConfig(id="mb_calc", params={"method": "havlena_odeh"}),
    )

    mc = MonteCarloSimulator(
        target_knot=material_balance,
        _config=KnotConfig(id="mc_sim", params={"n_samples": 1000}),
    )

    reserves = UncertaintyQuantifier(
        samples=mc,
        _config=KnotConfig(id="p10_p90"),
    )

result = await t.run(RunRequest(parameters={"smspec_bytes": raw_bytes, "pvt_table": pvt_df}))
```

## Anti-patterns

**Passing production time-series directly to MaterialBalanceCalculator without PvtTableProcessor** — raw PVT tables with unvalidated pressure ranges cause silent extrapolation errors in Bo/Rs lookup; always pre-process PVT first.

**Running MonteCarloSimulator with n_samples below 500** — P10/P90 estimates from small ensembles have high variance; the default of 1 000 samples is the recommended minimum for reserve reporting.

**Using DeclineCurveAnalyzer output as direct input to UncertaintyQuantifier without MonteCarloSimulator** — UncertaintyQuantifier expects a sample ensemble; passing a single deterministic result raises `EnsembleSizeError`.

## Constraints and gotchas

- `EclipseSmspecParser` requires the paired UNSMRY file at the same path; if only SMSPEC is provided it raises `MissingUnsmryError`.
- `CmgSsfileParser` supports CMG Results binary format version 3 and above; older formats must be exported to CSV before ingestion.
- `PvtTableProcessor` rejects tables with non-monotonic pressure columns and will raise `PvtMonotonicityError`.
- `MonteCarloSimulator` serialises the target knot's parameter distributions; knots with non-serialisable closures in `_config.params` will raise `DistributionSerializationError`.
- Install extra: `pip install pirn[reservoir]`

## Quick reference

| Task | How |
|------|-----|
| Parse Eclipse summary output | `EclipseSmspecParser(smspec=bytes_param)` |
| Parse CMG Results binary file | `CmgSsfileParser(ssfile=bytes_param)` |
| Validate and interpolate PVT table | `PvtTableProcessor(pvt=table_param)` |
| Fit Arps decline to sim production | `DeclineCurveAnalyzer(production=sim_summary)` |
| Apply Havlena-Odeh material balance | `MaterialBalanceCalculator(production=prod, pvt=pvt)` |
| Calculate STOIIP / GIIP | `StoiipCalculator(volumes=vol_param, pvt=pvt)` |
| Propagate uncertainty (Monte Carlo) | `MonteCarloSimulator(target_knot=calc_knot)` |
| Aggregate P10/P50/P90 reserves | `UncertaintyQuantifier(samples=mc_output)` |
| Compare two simulation scenarios | `SimulationResultComparator(base=run_a, compare=run_b)` |
| Compute RQI and FZI | `ReservoirQualityIndexer(core_data=core_param)` |

*See also: [oilgas AGENTIC_USE.md](../AGENTIC_USE.md)*
