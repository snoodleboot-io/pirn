# AGENTIC_USE — pirn.domains.oilgas

Provides upstream/midstream pipeline knots and file format connectors for seismic, well, production, reservoir, integrity, and geospatial workflows; does **not** include downstream processing, facilities engineering, or trading/commercial data.

---

## Mental model

The domain is organised as seven independent sub-packages under `pirn/domains/oilgas/`:

```
seismic     — SEG-Y ingest, NMO, stacking, migration, attributes
well        — LAS ingest, petrophysics (porosity, saturation, permeability), deviation
production  — SCADA ingest, GOR, water cut, decline, forecasting, well tests
reservoir   — Decline curve analysis, volumetrics, material balance, PVT, simulators
integrity   — ILI/corrosion, wall thickness, risk-based inspection, cathodic protection
geospatial  — CRS transforms, lease grouping, boundary proximity (requires pyproj)
workflows   — Pre-built SubTapestry pipelines that compose the sub-domains above
```

File format connectors live in `pirn/domains/connectors/file_formats/` (shared with other domains) and are wired into oilgas knots via their typed record dicts. Formats carry raw data to the knot boundary; knots own all domain logic.

Composition pattern: connector (`ObjectStoreReadSource`) → assembler (`SegyObjectStoreAssembler` / `LasObjectStoreAssembler`) → processing knots → optional `SubTapestry` workflow → `Tapestry` root. The ingestor pattern is abolished — assemblers receive already-materialised bytes and perform no I/O.

---

## Install

```bash
pip install "pirn[oilgas]"
```

Core extras (`segyio>=1.9`, `lasio>=0.31`) cover SEG-Y and LAS read/write and all sub-domain knots. XML-based formats (WITSML, PRODML, RESQML) and DLIS/SEG-D connectors are included; their transitive deps (`defusedxml`, `lxml`, `dlisio`) are declared automatically.

Additional opt-in dependencies:

| Library | Command | Enables |
|---------|---------|---------|
| `dlisio` | `pip install dlisio` | `DlisFormat` decode |
| `segpy` | `pip install segpy` | Improved `SegdFormat` decode |
| `pyproj` | `pip install pyproj` | `CoordinateSystemTransformer` |
| `pyspark` | `pip install "pirn[spark]"` | Distributed seismic volume processing |

---

## Source map

```
pirn/domains/oilgas/
├── __init__.py                        # empty public surface; import sub-packages directly
├── seismic/
│   ├── segy_header_parser.py          # validates binary + trace headers
│   ├── cmp_gather_extractor.py        # CMP gather extraction (sorted SEG-Y required)
│   ├── nmo_correction.py
│   ├── static_correction.py
│   ├── velocity_analyzer.py           # semblance-based velocity analysis
│   ├── stack_processor.py
│   ├── migration_processor.py         # Kirchhoff post-stack
│   ├── horizon_picker.py
│   ├── fault_detector.py
│   ├── seismic_attribute_calculator.py
│   ├── frequency_decomposer.py        # CWT / STFT spectral decomposition
│   └── subvolume_extractor.py
├── well/
│   ├── las_curve_validator.py
│   ├── deviation_survey_processor.py  # minimum-curvature 3D path
│   ├── well_path_calculator.py        # MD/TVD/THL/NS/EW
│   ├── formation_top_picker.py
│   ├── porosity_calculator.py         # density + neutron logs
│   ├── water_saturation_calculator.py # Archie / Simandoux
│   ├── permeability_estimator.py
│   ├── lithology_classifier.py
│   ├── log_normalizer.py              # cross-well histogram matching
│   ├── petrophysical_evaluator.py     # full evaluation pipeline
│   ├── mud_weight_calculator.py
│   ├── casing_design_evaluator.py
│   └── directional_drilling_planner.py
├── production/
│   ├── production_test_validator.py
│   ├── gas_oil_ratio_calculator.py
│   ├── water_cut_tracker.py
│   ├── water_injection_tracker.py
│   ├── decline_rate_estimator.py
│   ├── production_forecaster.py
│   ├── flowline_pressure_modeler.py   # Beggs-Brill
│   ├── artificial_lift_optimizer.py   # ESP / rod-pump
│   └── well_test_analyzer.py         # Horner plot, skin, kh
├── reservoir/
│   ├── decline_curve_analyzer.py      # Arps: exp / hyp / harmonic
│   ├── volumetric_estimator.py        # OOIP / GIIP
│   ├── material_balance_calculator.py # Havlena-Odeh
│   ├── pvt_table_processor.py
│   ├── relative_permeability_modeler.py
│   ├── type_curve_fitter.py           # unconventional reservoirs
│   ├── monte_carlo_simulator.py       # probabilistic reserves
│   ├── eclipse_smspec_parser.py
│   └── cmg_ssfile_parser.py
├── integrity/
│   ├── corrosion_rate_estimator.py
│   ├── wall_thickness_analyzer.py
│   ├── pig_run_data_processor.py
│   ├── risk_based_inspection_scorer.py  # API 581
│   ├── cathodic_protection_analyzer.py
│   └── energy_efficiency_kpi_calculator.py
├── geospatial/
│   ├── coordinate_system_transformer.py  # requires pyproj
│   ├── well_location_projector.py
│   ├── field_boundary_definer.py
│   ├── lease_block_grouper.py
│   └── boundary_proximity_checker.py
├── workflows/
│   ├── decline_curve_reserves_workflow.py
│   ├── field_production_reporting_workflow.py
│   ├── seismic_to_well_tie_workflow.py
│   └── wellbore_petrophysics_workflow.py
├── protocols/
│   ├── historian_connection.py        # SCADA / OPC-DA interface
│   ├── seismic_volume_store.py        # SEGY-SAP / in-house stores
│   └── well_data_service.py          # OSDU / PPDM REST API
├── assemblers/
│   ├── __init__.py
│   ├── las_object_store_assembler.py         — bytes → LASPayload via lasio
│   ├── segy_object_store_assembler.py        — bytes → SegyVolume via segyio
│   ├── scada_database_assembler.py           — list[tuple] → ScadaPayload
│   ├── mud_log_assembler.py                  — bytes → dict[str, Any]
│   └── well_completion_object_store_assembler.py — bytes → DrillingParameters
├── disassemblers/
│   ├── __init__.py
│   ├── las_object_store_disassembler.py      — LASPayload → bytes via lasio
│   └── segy_object_store_disassembler.py     — SegyVolume → bytes via segyio
└── types/
    ├── segy_trace.py
    ├── segy_volume.py
    ├── las_file.py
    ├── deviation_survey.py
    ├── drilling_parameters.py
    ├── formation_top.py
    ├── parsed_trace_header.py
    ├── pvt_table.py
    ├── scada_time_series.py
    └── well_path_3d.py
```

File format connectors (separate package path):
```
pirn/domains/connectors/file_formats/
├── segy_format.py
├── las_format.py
├── dlis_format.py
├── witsml_format.py
├── prodml_format.py
├── resqml_format.py
└── segd_format.py
```

---

## Assembler and Disassembler knots

Raw bytes and database rows cross the domain boundary through assembler knots. No ingestor classes exist — the ingestor pattern is abolished.

### Assemblers

| Knot | Input | Output | Library |
|------|-------|--------|---------|
| `LasObjectStoreAssembler` | `bytes` + `well_id` | `LASPayload` | lasio |
| `SegyObjectStoreAssembler` | `bytes` + `volume_id` | `SegyVolume` | segyio |
| `ScadaDatabaseAssembler` | `list[tuple]` + tag/interval metadata | `ScadaPayload` | stdlib |
| `MudLogAssembler` | `bytes` | `dict[str, Any]` | stdlib |
| `WellCompletionObjectStoreAssembler` | `bytes` + `well_id` | `DrillingParameters` | stdlib |

### Disassemblers

| Knot | Input | Output | Library |
|------|-------|--------|---------|
| `LasObjectStoreDisassembler` | `LASPayload` | `bytes` | lasio |
| `SegyObjectStoreDisassembler` | `SegyVolume` | `bytes` | segyio |

All assemblers and disassemblers extend `Assembler` / `Disassembler` from `pirn.core`. None perform I/O.

Example pipeline (LAS):

```python
from pirn.domains.oilgas.assemblers.las_object_store_assembler import LasObjectStoreAssembler

with Tapestry() as t:
    raw = ObjectStoreReadSource(bucket="wells", key="GR-01.las", _config=KnotConfig(id="raw"))
    payload = LasObjectStoreAssembler(body=raw, well_id="GR-01", _config=KnotConfig(id="las"))
    PorosityKnot(payload=payload, _config=KnotConfig(id="porosity"))
```

---

## Sub-domain guide

| Sub-domain | Purpose | Representative knots |
|------------|---------|---------------------|
| `seismic` | Seismic acquisition and processing, from raw SEG-Y to interpreted attributes | `SegyObjectStoreAssembler`, `CmpGatherExtractor`, `NmoCorrection`, `MigrationProcessor`, `SeismicAttributeCalculator` |
| `well` | Well log ingestion and full petrophysical evaluation | `LasObjectStoreAssembler`, `PorosityCalculator`, `WaterSaturationCalculator`, `PetrophysicalEvaluator`, `DeviationSurveyProcessor`, `WellCompletionObjectStoreAssembler`, `MudLogAssembler` |
| `production` | Real-time and historical production monitoring and optimisation | `ScadaDatabaseAssembler`, `GasOilRatioCalculator`, `WaterCutTracker`, `ArtificialLiftOptimizer`, `WellTestAnalyzer` |
| `reservoir` | Reservoir engineering, simulation output parsing, probabilistic reserves | `DeclineCurveAnalyzer`, `VolumetricEstimator`, `MaterialBalanceCalculator`, `MonteCarloSimulator`, `EclipseSmspecParser` |
| `integrity` | Asset integrity, inspection scoring, corrosion, GHG KPIs | `PigRunDataProcessor`, `RiskBasedInspectionScorer`, `CorrosionRateEstimator`, `EnergyEfficiencyKpiCalculator` |
| `geospatial` | CRS transforms, lease grouping, boundary proximity checks | `CoordinateSystemTransformer`, `LeaseBlockGrouper`, `BoundaryProximityChecker` |
| `workflows` | Pre-built end-to-end `SubTapestry` pipelines | `WellborePetrophysicsWorkflow`, `SeismicToWellTieWorkflow`, `DeclineCurveReservesWorkflow`, `FieldProductionReportingWorkflow` |

---

## File format connectors

| Format | Class | Required extra | Record shape (one dict per…) | Read | Write |
|--------|-------|---------------|------------------------------|------|-------|
| SEG-Y | `SegyFormat` | `segyio` (bundled in `oilgas`) | trace: `trace_index`, `header` (dict), `data` (float32 bytes big-endian) | yes | yes |
| LAS | `LasFormat` | `lasio` (bundled in `oilgas`) | file: `curves` (list[str]), `data` (list[list[float]]), `metadata` (dict) | yes | yes |
| DLIS | `DlisFormat` | `pip install dlisio` | channel×frame: `frame_name`, `channel_name`, `data` (bytes; `b""` on corrupt channel) | yes | no |
| WITSML | `WitsmlFormat` | `defusedxml`, `lxml` (transitive) | `<log>`/`<well>` element: flat dict, two-level nesting as `"parent.child"` | yes | yes |
| PRODML | `ProdmlFormat` | `defusedxml`, `lxml` (transitive) | top-level child element: flat dict (same shape as WITSML) | yes | yes |
| RESQML | `ResqmlFormat` | `defusedxml`, `lxml` (transitive) | top-level child element: flat dict; **HDF5 sidecar arrays not included** | yes | yes |
| SEG-D | `SegdFormat` | `segpy` optional | file (header only): `record_length`, `channel_count`, `sample_interval`, `raw_header` | yes | no |

Import paths:
```python
from pirn.connectors.file_formats.segy_format import SegyFormat
from pirn.connectors.file_formats.las_format import LasFormat
from pirn.connectors.file_formats.witsml_format import WitsmlFormat
```

---

## Canonical pattern

SEG-Y ingest → trace normalisation → attribute extraction in a single Tapestry:

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.connectors.knots.object_store_read_source import ObjectStoreReadSource
from pirn.domains.oilgas.assemblers.segy_object_store_assembler import SegyObjectStoreAssembler
from pirn.tapestry import Tapestry

with Tapestry() as t:
    raw = ObjectStoreReadSource(
        bucket="seismic-data",
        key="survey.segy",
        _config=KnotConfig(id="raw"),
    )
    volume = SegyObjectStoreAssembler(
        body=raw,
        volume_id="block-42a",
        _config=KnotConfig(id="volume"),
    )
    # downstream processing knots wire off volume...
```

For well petrophysics, use the pre-built workflow instead of wiring knots manually:

```python
from pirn.domains.oilgas.workflows.wellbore_petrophysics_workflow import WellborePetrophysicsWorkflow
```

---

## Anti-patterns

**Passing raw bytes to domain knots.** Knots accept typed domain objects (`SegyVolume`, `LASFile`, `ScadaTimeSeries`). Always decode bytes through the appropriate `FileFormat` first, then pass the resulting records through an assembler knot.

**Reusing `SegyFormat` across large 3D volumes without splitting.** `BatchFileFormat` buffers the entire file before decoding. For large surveys, split into inline sub-ranges before calling `decode()`.

**Using `SegyFormat.encode()` expecting IEEE float output.** The encoder always writes IBM float (format 1). If a downstream tool requires IEEE float or integer formats, apply the conversion outside pirn.

**Feeding unsorted SEG-Y into `CmpGatherExtractor`.** The extractor requires the input volume to be sorted by CMP. Run `SegyHeaderParser` first and assert geometry sorting before extracting gathers.

**Calling `DlisFormat.encode()`.** DLIS write is not supported and will raise `NotImplementedError`. Convert DLIS data to LAS via `LasFormat` for any write-back path.

**Relying on RESQML or WITSML connectors for array data.** Both connectors flatten the XML envelope only. HDF5 sidecar arrays (RESQML grid geometry/properties, WITSML time-depth data) are not decoded — they appear as raw text or are absent.

**Calling geospatial knots without `pyproj`.** `CoordinateSystemTransformer` and dependants raise `ImportError` at runtime without `pyproj`. Install explicitly; it is not bundled in `pirn[oilgas]`.

---

## Constraints and gotchas

- **Knots are slim stubs.** All oilgas knots validate inputs and return typed result references. The real computation (segyio, lasio, scipy) is invoked at runtime inside `process()`. The graph imports and type-checks without the extras installed; only `process()` calls fail.
- **`LasObjectStoreAssembler` depth unit.** Accepted values are `"m"` and `"ft"` only. Anything else raises `ValueError` at construction time.
- **SEG-D without `segpy`.** The pure-Python fallback reads only the 32-byte General Header Block 1. Vendor-specific Extended Header Blocks are silently skipped. Install `segpy` for fuller decode.
- **DLIS corrupt channels.** A channel that cannot be read emits `data=b""` rather than raising. Downstream QC knots must check for empty `data` bytes explicitly.
- **SEG-Y encode geometry.** Encoded files have `sorting=None` (unsorted). If a downstream consumer requires sorted geometry, call `segyio` directly after pirn writes the file.
- **`ScadaDatabaseAssembler` receives already-fetched rows.** Pass pre-fetched `list[tuple]` rows plus tag and interval metadata. The assembler performs no I/O and does not require a live connection.
- **`MonteCarloSimulator` is probabilistic.** Results differ across runs unless the seed is fixed via the knot's configuration. Fix the seed in tests.
- **`EclipseSmspecParser` / `CmgSsfileParser` are parse-only.** They produce Python dicts from simulator summary files; they do not drive or control the simulators.

---

## Quick reference

| Task | Knot / Format |
|------|--------------|
| Ingest SEG-Y file | `ObjectStoreReadSource` → `SegyObjectStoreAssembler` |
| Validate trace headers | `SegyHeaderParser` |
| Extract CMP gathers | `CmpGatherExtractor` (sorted SEG-Y required) |
| NMO + stack | `NmoCorrection` → `StackProcessor` |
| Post-stack migration | `MigrationProcessor` |
| Seismic attributes | `SeismicAttributeCalculator` |
| Spectral decomposition | `FrequencyDecomposer` |
| Ingest LAS well log | `ObjectStoreReadSource` → `LasObjectStoreAssembler` |
| Full petrophysical eval | `PetrophysicalEvaluator` (or `WellborePetrophysicsWorkflow`) |
| 3D well path from survey | `DeviationSurveyProcessor` → `WellPathCalculator` |
| Lithology classification | `LithologyClassifier` |
| Ingest SCADA rows | `ScadaDatabaseAssembler` (rows from `DatabaseQuerySource`) |
| Water cut tracking | `WaterCutTracker` |
| Decline curve fit | `DeclineCurveAnalyzer` (Arps) |
| Probabilistic reserves | `MonteCarloSimulator` |
| Material balance | `MaterialBalanceCalculator` (Havlena-Odeh) |
| Parse Eclipse output | `EclipseSmspecParser` |
| Parse CMG output | `CmgSsfileParser` |
| ILI / pig run | `PigRunDataProcessor` → `RiskBasedInspectionScorer` |
| CRS transform | `CoordinateSystemTransformer` (requires `pyproj`) |
| Seismic-to-well tie | `SeismicToWellTieWorkflow` |
| Field production report | `FieldProductionReportingWorkflow` |
| Ingest WITSML drilling data | `WitsmlFormat` |
| Ingest PRODML production data | `ProdmlFormat` |
| Ingest RESQML reservoir model | `ResqmlFormat` (XML envelope only) |
| Decode DLIS wireline log | `DlisFormat` (requires `dlisio`; decode only) |
| Decode SEG-D field data | `SegdFormat` (decode only; `segpy` optional) |

---

*See also: [pirn AGENTIC_USE.md](../../../AGENTIC_USE.md)*
