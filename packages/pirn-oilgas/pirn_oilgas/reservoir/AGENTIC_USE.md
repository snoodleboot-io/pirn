Performs reservoir engineering calculations — material balance, PVT table assembly, decline curve analysis, volumetric and Monte-Carlo reserves estimation, and simulation result parsing. Does NOT run reservoir simulators; it processes their output files (CMG SSFILE, Eclipse SMSPEC).

## Mental model

Reservoir engineering in pirn is a calculation layer that sits downstream of simulator output and upstream of decision-support reports. Simulation parsers ingest binary or text output files and emit `ScadaTimeSeries` references; calculation knots (material balance, volumetrics, decline curves) operate on those series along with PVT and production inputs; `MonteCarloSimulator` wraps a deterministic estimate in a sampling ensemble to propagate parameter uncertainty into a P10/P50/P90 reserve distribution.

Every knot in this sub-package is imported from the module that defines it. `pirn_oilgas/reservoir/__init__.py` re-exports nothing (`__all__` is empty) — the house convention forbids import forwarding — so importing a class straight from the `pirn_oilgas.reservoir` package raises `ImportError`.

## Source map

```
├── cmg_ssfile_parser.py               CmgSsfileParser               — parses a CMG SSFILE text summary into a ScadaTimeSeries reference
├── decline_curve_analyzer.py          DeclineCurveAnalyzer          — fits an Arps decline (exponential, hyperbolic, harmonic) to a rate series
├── eclipse_smspec_parser.py           EclipseSmspecParser           — parses an Eclipse SMSPEC binary into a ScadaTimeSeries reference
├── material_balance_calculator.py     MaterialBalanceCalculator     — solves a Havlena-Odeh-style material balance for OOIP / OGIP
├── monte_carlo_simulator.py           MonteCarloSimulator           — samples a deterministic estimate over N trials into P10 / P50 / P90
├── pressure_transient_analyzer.py     PressureTransientAnalyzer     — estimates permeability, skin, and PI from pressure transient test data
├── production_allocation_engine.py    ProductionAllocationEngine    — allocates field totals to individual wells by test ratios or regression
├── pvt_table_processor.py             PvtTableProcessor             — builds a PVT lookup-table reference from configured grid sizes
├── relative_permeability_modeler.py   RelativePermeabilityModeler   — fits a kr / Sw model and returns the resulting parameter table
├── reserves_estimation_pipeline.py    ReservesEstimationPipeline    — estimates 1P / 2P / 3P reserves and EUR from a production history
├── type_curve_fitter.py               TypeCurveFitter               — fits a single type curve to a representative rate series
└── volumetric_estimator.py            VolumetricEstimator           — computes OOIP from area / thickness / porosity / Sw / FVF
```

## Canonical pattern

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_oilgas.reservoir.eclipse_smspec_parser import EclipseSmspecParser
from pirn_oilgas.reservoir.material_balance_calculator import MaterialBalanceCalculator
from pirn_oilgas.reservoir.monte_carlo_simulator import MonteCarloSimulator
from pirn_oilgas.reservoir.pvt_table_processor import PvtTableProcessor
from pirn_oilgas.reservoir.volumetric_estimator import VolumetricEstimator

with Tapestry() as t:
    smspec_path = Parameter("smspec_path", str, _config=KnotConfig(id="smspec_path"))

    oil_rate = EclipseSmspecParser(
        smspec_path=smspec_path,
        vector_name="WOPR:W1",
        _config=KnotConfig(id="parse_smspec"),
    )

    pvt = PvtTableProcessor(
        fluid_id="RESERVOIR-A",
        pressure_count=40,
        temperature_count=5,
        _config=KnotConfig(id="pvt_process"),
    )

    balance = MaterialBalanceCalculator(
        pvt=pvt,
        cumulative_oil_stb=1_250_000.0,
        cumulative_gas_mscf=2_400_000.0,
        cumulative_water_stb=310_000.0,
        average_pressure_psi=2_850.0,
        _config=KnotConfig(id="mb_calc"),
    )

    ooip = VolumetricEstimator(
        area_acres=640.0,
        net_thickness_ft=45.0,
        porosity_fraction=0.18,
        water_saturation_fraction=0.32,
        formation_volume_factor=1.25,
        _config=KnotConfig(id="ooip"),
    )

    reserves = MonteCarloSimulator(
        deterministic_estimate=ooip,
        trial_count=1000,
        seed=7,
        _config=KnotConfig(id="p10_p50_p90"),
    )

result = await t.run(RunRequest(parameters={"smspec_path": "/data/CASE.SMSPEC"}))
```

## Anti-patterns

**Importing from the sub-package** — naming a class on the `pirn_oilgas.reservoir` package itself (rather than on `pirn_oilgas.reservoir.monte_carlo_simulator`) raises `ImportError`; the `__init__.py` deliberately re-exports nothing. Import from the defining module instead.

**Feeding `MonteCarloSimulator.deterministic_estimate` a knot that does not return a float** — it is annotated `Knot` and its `process()` expects a `float`; `MaterialBalanceCalculator` and `ReservesEstimationPipeline` both return `dict[str, float]`, so wire `VolumetricEstimator` (returns `float`) or select a single value first.

**Wiring an `EclipseSmspecParser` / `CmgSsfileParser` output straight into `DeclineCurveAnalyzer` or `TypeCurveFitter`** — the parsers return a `ScadaTimeSeries` *reference* (metadata only, no samples), while the curve fitters require a `ScadaPayload` (metadata + the float64 sample array) and raise `TypeError` otherwise.

**Running `MonteCarloSimulator` with a small `trial_count`** — P10/P90 spread from small ensembles has high variance; `trial_count` must be a positive int, and 1 000 trials is the practical minimum for reserve reporting.

## Constraints and gotchas

- `EclipseSmspecParser` needs the `resfo` reader: it raises `ValueError` on an empty `smspec_path` or `vector_name`, `FileNotFoundError` when the file is missing, and `KeyError` when the named vector is not present in the summary.
- `CmgSsfileParser` reads the SSFILE text summary and raises the same `ValueError` / `FileNotFoundError` / `KeyError` family.
- `PvtTableProcessor` raises `ValueError` for an empty `fluid_id` or a non-positive `pressure_count` / `temperature_count`.
- `DeclineCurveAnalyzer.method` must be one of `exponential`, `hyperbolic`, `harmonic`; anything else raises `ValueError`. Hyperbolic fits go through `scipy.optimize`.
- `ReservesEstimationPipeline` requires `economic_limit_bopd > 0` and `royalty_rate` in `[0, 1)`, and returns zeros when the production history holds fewer than two rate points.
- Install extra: `pip install "pirn-oilgas[oilgas]"` (pulls `resfo`, `scipy`, `lasio`, `segyio`).

## Quick reference

| Task | How |
|------|-----|
| Parse an Eclipse summary vector | `EclipseSmspecParser(smspec_path=path, vector_name="WOPR:W1", _config=...)` |
| Parse a CMG SSFILE vector | `CmgSsfileParser(ssfile_path=path, vector_name="WOPR", _config=...)` |
| Build a PVT lookup table | `PvtTableProcessor(fluid_id="A", pressure_count=40, temperature_count=5, _config=...)` |
| Fit an Arps decline to a rate series | `DeclineCurveAnalyzer(rate_series=payload, method="hyperbolic", _config=...)` |
| Apply Havlena-Odeh material balance | `MaterialBalanceCalculator(pvt=pvt, cumulative_oil_stb=..., cumulative_gas_mscf=..., cumulative_water_stb=..., average_pressure_psi=..., _config=...)` |
| Compute OOIP volumetrically | `VolumetricEstimator(area_acres=..., net_thickness_ft=..., porosity_fraction=..., water_saturation_fraction=..., formation_volume_factor=..., _config=...)` |
| Propagate uncertainty into P10/P50/P90 | `MonteCarloSimulator(deterministic_estimate=ooip, trial_count=1000, seed=7, _config=...)` |
| Estimate 1P/2P/3P reserves and EUR | `ReservesEstimationPipeline(production_history=history, economic_limit_bopd=20.0, royalty_rate=0.125, _config=...)` |
| Interpret a pressure transient test | `PressureTransientAnalyzer(test_data=test, wellbore_radius_ft=..., formation_thickness_ft=..., fluid_viscosity_cp=..., _config=...)` |
| Allocate field totals to wells | `ProductionAllocationEngine(field_totals=totals, well_tests=tests, allocation_method="ratio", _config=...)` |
| Fit a relative-permeability model | `RelativePermeabilityModeler(pvt=pvt, method="corey", _config=...)` |
| Fit a type curve | `TypeCurveFitter(rate_series=payload, _config=...)` |

*See also: [oilgas AGENTIC_USE.md](../AGENTIC_USE.md)*
