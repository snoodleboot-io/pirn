# Knot Design Rules Audit Report

**Scan Date:** 2026-05-06  
**Method:** Automated AST scan, all rules R1-R11 + Security

## Legend

| Column | Rule | Details |
|--------|------|---------|
| R1 | `__init__` body is ONLY `super().__init__(...)` | No validation, assignments, or logic |
| R2 | Every `__init__` param (except `_config`, `**kwargs`) appears by same name in `process()` | Ensures direct testability |
| R3 | No `raise` statements in `__init__` | All validation deferred to `process()` |
| R4 | No `self._x` assignments storing inputs | Inputs arrive fresh in `process()` |
| R5 | No `@property` exposing stored inputs or derived strings | Computed values via private helpers only |
| R6 | Opaque resources use a dedicated vending Knot, not passed directly | Live connections/sessions cannot travel the graph |
| R7 | `__init__` params use Knot types or `Knot \| scalar` — NOT plain scalars | Ensures graph wiring and lineage |
| R8 | If inherits `SubTapestry`: `process()` calls `self._run_inner()` | N/A for plain `Knot`/`Source`/`Sink` |
| R9 | Quality assessment Knots returning `QualityReport` use `*Check` suffix, not `*Gate` | N/A if not a quality assessment Knot |
| R10-Algo | Module docstring contains `Algorithm:` section | Step-by-step description |
| R10-Math | Module docstring contains `Math:` section | Always required — N/A confirmed only after reading `process()` |
| R10-Refs | Module docstring contains `References:` section | N/A if entirely pirn-native |
| Sec | Any `hashlib.md5()` call includes `usedforsecurity=False` | N/A if no md5 usage |
| Step11 | Tests call `process()` directly with plain values under `tests/unit/` | Not just via Tapestry.run() |
| Step12 | All applicable rules pass AND Step11 passes | Ready for ruff/pyright/pytest |

**Cell values:** `[x]` = compliant · `[ ]` = violation · `N/A` = rule does not apply

---

## Audit Table

### Group 1 — geospatial/boundary_proximity_checker.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/geospatial/boundary_proximity_checker.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 2 — geospatial/coordinate_system_transformer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/geospatial/coordinate_system_transformer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 3 — geospatial/fault_proximity_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/geospatial/fault_proximity_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 4 — geospatial/field_boundary_definer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/geospatial/field_boundary_definer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 5 — geospatial/infrastructure_asset_mapper.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/geospatial/infrastructure_asset_mapper.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 6 — geospatial/lease_block_grouper.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/geospatial/lease_block_grouper.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 7 — geospatial/well_location_projector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/geospatial/well_location_projector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 8 — integrity/cathodic_protection_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/integrity/cathodic_protection_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 9 — integrity/corrosion_rate_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/integrity/corrosion_rate_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 10 — integrity/energy_efficiency_kpi_calculator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/integrity/energy_efficiency_kpi_calculator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 11 — integrity/gas_chromatography_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/integrity/gas_chromatography_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 12 — integrity/pig_run_data_processor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/integrity/pig_run_data_processor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 13 — integrity/psv_test_record_parser.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/integrity/psv_test_record_parser.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 14 — integrity/risk_based_inspection_scorer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/integrity/risk_based_inspection_scorer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 15 — integrity/scope1_emissions_reporter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/integrity/scope1_emissions_reporter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 16 — integrity/wall_thickness_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/integrity/wall_thickness_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 17 — production/artificial_lift_optimizer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/artificial_lift_optimizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 18 — production/decline_rate_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/decline_rate_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 19 — production/downtime_event_classifier.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/downtime_event_classifier.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 20 — production/esp_health_monitor.py

`__init__` accepts only `**kwargs` — R2 and R7 are N/A (no named scalar params beyond **kwargs).

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/esp_health_monitor.py` | [x] | N/A | [x] | [x] | [x] | N/A | N/A | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 21 — production/flaring_measurement_processor.py

`__init__` accepts only `**kwargs` — R2 and R7 are N/A.

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/flaring_measurement_processor.py` | [x] | N/A | [x] | [x] | [x] | N/A | N/A | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 22 — production/flowline_pressure_modeler.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/flowline_pressure_modeler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 23 — production/gas_lift_optimizer.py

`__init__` accepts only `**kwargs` — R2 and R7 are N/A.

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/gas_lift_optimizer.py` | [x] | N/A | [x] | [x] | [x] | N/A | N/A | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 24 — production/gas_oil_ratio_calculator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/gas_oil_ratio_calculator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 25 — production/production_forecaster.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/production_forecaster.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 26 — production/production_rate_normalizer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/production_rate_normalizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 27 — production/production_test_validator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/production_test_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 28 — production/rod_pump_optimizer.py

`__init__` accepts only `**kwargs` — R2 and R7 are N/A.

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/rod_pump_optimizer.py` | [x] | N/A | [x] | [x] | [x] | N/A | N/A | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 29 — production/scada_historian_ingester.py

`connection: Knot | HistorianConnection` is the approved ScadaHistorianIngester pattern — not an R6 violation per design rules.

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/scada_historian_ingester.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 30 — production/separator_test_processor.py

`__init__` accepts only `**kwargs` — R2 and R7 are N/A.

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/separator_test_processor.py` | [x] | N/A | [x] | [x] | [x] | N/A | N/A | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 31 — production/tank_gauging_processor.py

`__init__` accepts only `**kwargs` — R2 and R7 are N/A.

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/tank_gauging_processor.py` | [x] | N/A | [x] | [x] | [x] | N/A | N/A | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 32 — production/water_cut_tracker.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/water_cut_tracker.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 33 — production/water_injection_tracker.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/water_injection_tracker.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 34 — production/well_test_analyzer.py

`__init__` accepts only `**kwargs` — R2 and R7 are N/A.

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/production/well_test_analyzer.py` | [x] | N/A | [x] | [x] | [x] | N/A | N/A | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 35 — reservoir/cmg_ssfile_parser.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/reservoir/cmg_ssfile_parser.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 36 — reservoir/decline_curve_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/reservoir/decline_curve_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 37 — reservoir/eclipse_smspec_parser.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/reservoir/eclipse_smspec_parser.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 38 — reservoir/material_balance_calculator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/reservoir/material_balance_calculator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 39 — reservoir/monte_carlo_simulator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/reservoir/monte_carlo_simulator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 40 — reservoir/pressure_transient_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/reservoir/pressure_transient_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 41 — reservoir/production_allocation_engine.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/reservoir/production_allocation_engine.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 42 — reservoir/pvt_table_processor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/reservoir/pvt_table_processor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 43 — reservoir/relative_permeability_modeler.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/reservoir/relative_permeability_modeler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 44 — reservoir/reserves_estimation_pipeline.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/reservoir/reserves_estimation_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 45 — reservoir/type_curve_fitter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/reservoir/type_curve_fitter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 46 — reservoir/volumetric_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/reservoir/volumetric_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 47 — seismic/acoustic_impedance_inverter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/acoustic_impedance_inverter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 48 — seismic/cmp_gather_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/cmp_gather_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 49 — seismic/fault_detector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/fault_detector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 50 — seismic/fk_denoising_knot.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/fk_denoising_knot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 51 — seismic/frequency_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/frequency_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 52 — seismic/horizon_picker.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/horizon_picker.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 53 — seismic/instantaneous_attribute_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/instantaneous_attribute_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 54 — seismic/migration_processor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/migration_processor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 55 — seismic/nmo_correction.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/nmo_correction.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 56 — seismic/rms_amplitude_window_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/rms_amplitude_window_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 57 — seismic/segy_file_ingester.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/segy_file_ingester.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 58 — seismic/segy_header_parser.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/segy_header_parser.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 59 — seismic/seismic_attribute_calculator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/seismic_attribute_calculator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 60 — seismic/seismic_bandpass_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/seismic_bandpass_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 61 — seismic/seismic_qc_gate.py

Does not return `QualityReport` — R9 is N/A. (Note: the `Gate` suffix naming is a separate concern tracked outside this audit.)

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/seismic_qc_gate.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 62 — seismic/spherical_divergence_gain.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/spherical_divergence_gain.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 63 — seismic/stack_processor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/stack_processor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 64 — seismic/static_correction.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/static_correction.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 65 — seismic/subvolume_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/subvolume_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 66 — seismic/velocity_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/velocity_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 67 — seismic/velocity_model_builder.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/seismic/velocity_model_builder.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 68 — well/casing_design_evaluator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/casing_design_evaluator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 69 — well/core_to_log_depth_matcher.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/core_to_log_depth_matcher.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 70 — well/depth_shift_corrector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/depth_shift_corrector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 71 — well/deviation_survey_processor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/deviation_survey_processor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 72 — well/directional_drilling_planner.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/directional_drilling_planner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 73 — well/environmental_correction_applicator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/environmental_correction_applicator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 74 — well/formation_top_picker.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/formation_top_picker.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 75 — well/las_curve_validator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/las_curve_validator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 76 — well/las_file_ingester.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/las_file_ingester.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 77 — well/lithology_classifier.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/lithology_classifier.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 78 — well/log_normalizer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/log_normalizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 79 — well/log_spike_remover.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/log_spike_remover.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 80 — well/mud_logging_ingester.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/mud_logging_ingester.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 81 — well/mud_weight_calculator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/mud_weight_calculator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 82 — well/permeability_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/permeability_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 83 — well/petrophysical_evaluator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/petrophysical_evaluator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 84 — well/porosity_calculator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/porosity_calculator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 85 — well/vshale_calculator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/vshale_calculator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 86 — well/water_saturation_calculator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/water_saturation_calculator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 87 — well/well_completion_ingester.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/well_completion_ingester.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 88 — well/well_path_calculator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/well_path_calculator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 89 — well/witsml_drilling_monitor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/well/witsml_drilling_monitor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 90 — workflows/decline_curve_reserves_workflow.py

`connection: HistorianConnection` directly wired follows the approved ScadaHistorianIngester pattern — not an R6 violation per design rules. Inherits `SubTapestry`; `process()` calls `self._run_inner(inner)` → R8 [x].

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/workflows/decline_curve_reserves_workflow.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 91 — workflows/field_production_reporting_workflow.py

`connection: HistorianConnection` directly wired follows the approved ScadaHistorianIngester pattern — not an R6 violation per design rules. Inherits `SubTapestry`; `process()` calls `self._run_inner(inner)` → R8 [x].

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/workflows/field_production_reporting_workflow.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 92 — workflows/seismic_to_well_tie_workflow.py

Inherits `SubTapestry`; `process()` calls `self._run_inner(inner)` → R8 [x]. No opaque resource in `__init__` → R6 N/A.

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/workflows/seismic_to_well_tie_workflow.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 93 — workflows/wellbore_petrophysics_workflow.py

Inherits `SubTapestry`; `process()` calls `self._run_inner(inner)` → R8 [x]. No opaque resource in `__init__` → R6 N/A.

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/oilgas/workflows/wellbore_petrophysics_workflow.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | [x] | N/A | [x] | N/A | [x] | N/A | [x] | [x] |
