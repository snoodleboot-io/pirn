# Oil & Gas Domain

pirn's oil & gas domain provides pipeline knots and file format connectors for the full upstream/midstream data stack: seismic acquisition and processing (SEG-Y, SEG-D), well logging and petrophysics (LAS, DLIS), drilling operations (WITSML), production monitoring (PRODML, SCADA), and reservoir characterisation (RESQML, Eclipse/CMG simulator output). All formats are implemented as standard `BatchFileFormat` classes and integrate directly with pirn's lineage and audit machinery.

---

## Format Reference

| Format | Class | Spec | Record shape | Read | Write | Dependency |
|---|---|---|---|---|---|---|
| SEG-Y | `SegyFormat` | SEG rev 1/2 | One dict per trace: `trace_index`, `header`, `data` (float32 bytes) | yes | yes | `segyio` |
| LAS | `LasFormat` | LAS 2.0 / 3.0 | One dict per file: `curves`, `data`, `metadata` | yes | yes | `lasio` |
| DLIS | `DlisFormat` | RP66 v1 | One dict per channel per frame: `frame_name`, `channel_name`, `data` | yes | **no** | `dlisio` |
| WITSML | `WitsmlFormat` | WITSML 1.4.1 | One flat dict per `<log>` / `<well>` element | yes | yes | `defusedxml`, `lxml` |
| PRODML | `ProdmlFormat` | PRODML 1-series | One flat dict per top-level child element | yes | yes | `defusedxml`, `lxml` |
| RESQML | `ResqmlFormat` | RESQML v2 | One flat dict per top-level child element | yes | yes | `defusedxml`, `lxml` |
| SEG-D | `SegdFormat` | SEG-D rev 3 | One dict per file: `record_length`, `channel_count`, `sample_interval`, `raw_header` | yes | **no** | stdlib only |

---

## SEG-Y (`SegyFormat`)

SEG-Y is the industry-standard format for seismic reflection data. Each file contains a textual file header, a binary file header, and a sequence of traces with 240-byte trace headers and floating-point sample data. Backed by `segyio`.

**Constructor params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `sample_rate` | `int` | `2000` | Sample interval in microseconds used when creating new SEG-Y files |

**Record shape (one per trace):**

```python
{
    "trace_index": int,
    "header":      dict[str, Any],   # segyio trace header fields (all integer-valued)
    "data":        bytes,            # big-endian float32 sample array
}
```

**Example:**

```python
from pirn.connectors.file_formats.segy_format import SegyFormat

fmt = SegyFormat(sample_rate=4000)   # 4 ms sample interval
records = await fmt.decode(segy_bytes)
# records[0]["header"]["INLINE_3D"], records[0]["data"] ...
```

**Limitations:**

- The whole file is buffered before decoding (inherits `BatchFileFormat`). For very large 3D volumes, consider streaming by splitting the volume into inline sub-ranges before decoding.
- Encode always uses IBM float (format 1). IEEE float and integer formats are not supported on the write path.
- Geometry sorting (`segyio.spec.sorting`) is set to `None` on encode, producing an unsorted file. Apply sorting and geometry assignment in a downstream step using `segyio` directly if needed.

---

## LAS (`LasFormat`)

LAS (Log ASCII Standard) is a widely-used ASCII/binary format for borehole well log data. Backed by `lasio`.

**Constructor params:** none.

**Record shape (one per file):**

```python
{
    "curves":   list[str],           # curve names in column order; curves[0] is depth
    "data":     list[list[float]],   # rows; each row = one depth sample across all curves
    "metadata": dict[str, Any],      # well/params/curves/other header sections flattened
                                     # as "section.key": value
}
```

**Example:**

```python
from pirn.connectors.file_formats.las_format import LasFormat

fmt = LasFormat()
records = await fmt.decode(las_bytes)
curves = records[0]["curves"]        # ["DEPT", "GR", "RHOB", "NPHI", ...]
depth_values = [row[0] for row in records[0]["data"]]
```

---

## DLIS (`DlisFormat`) — decode only

DLIS (Digital Log Interchange Standard, RP66 v1) is a complex binary well log format used for LWD/MWD and wireline log deliverables. Writing DLIS is not supported; use an upstream tool such as `dlisio` or vendor acquisition software directly.

**Why decode-only?** The DLIS specification defines a highly nested logical structure (logical records, frames, channels, templates) with variable-length encoding and optional encryption. No production-quality open-source Python writer for RP66 v1 exists; generating well-formed DLIS from scratch requires full specification compliance that is out of scope for a general-purpose connector.

**Record shape (one per channel per frame):**

```python
{
    "frame_name":   str,
    "channel_name": str,
    "data":         bytes,   # raw numpy array bytes from channel.curves()
}
```

If a channel's data cannot be read (e.g. due to corrupted frames), `data` is `b""` rather than raising — the record is emitted so downstream quality knots can flag the gap.

**Encoding:** raises `NotImplementedError`.

---

## WITSML (`WitsmlFormat`)

WITSML (Wellsite Information Transfer Standard Markup Language) is an XML-based standard for drilling and well operations data. Backed by `defusedxml` (parse) and `lxml` (write).

**Record shape (one per top-level `<log>` or `<well>` element):**

```python
{
    "tag":              value,   # flat dict; child.tag → child.text
    "child.grandchild": value,   # two-level nesting flattened as "parent.child"
    ...
}
```

**Write:** reconstructs a minimal WITSML 1.4.1 XML document wrapped in a `<wellLogs>` root element.

**Limitations:** Only the XML envelope is processed. HDF5 sidecar data and Time-Depth data arrays are out of scope; they are passed through as raw text values if present.

---

## PRODML (`ProdmlFormat`)

PRODML (Production Markup Language) is an Energistics XML standard for oil and gas production data. Record shape and flattening behaviour are identical to `WitsmlFormat`. Write reconstructs a minimal PRODML document with a `<prodmlObjects>` root.

---

## RESQML (`ResqmlFormat`)

RESQML (Reservoir Characterization and Simulation Markup Language) is an Energistics XML standard for reservoir geometry, property, and simulation data. **Only the XML envelope is processed** — HDF5 sidecar files that carry array data (grid geometry, property values) are out of scope. Record shape and flattening behaviour are identical to `WitsmlFormat`.

---

## SEG-D (`SegdFormat`) — decode only

SEG-D is a binary tape format used to record seismic field data. It predates SEG-Y and is used primarily by acquisition crews in the field.

**Why decode-only?** SEG-D encodes raw field recordings with vendor-specific Extended Header Blocks, auxiliary traces, and BCD-coded fields that vary between recorder generations. Reliably round-tripping all variants requires deep vendor-specific knowledge; writing SEG-D output is not a standard data-pipeline need — re-acquisition is always performed by the recording instrument.

**Record shape (one per file — General Header Block 1 only):**

```python
{
    "record_length":   int,     # milliseconds
    "channel_count":   int,
    "sample_interval": float,   # milliseconds
    "raw_header":      bytes,   # first 32 bytes of the file
}
```

If `segpy` is installed it is used for decoding; otherwise a minimal pure-Python parser reads the 32-byte General Header Block 1 only. Either path emits the same record shape.

**Encoding:** raises `NotImplementedError`.

---

## Sub-domains

### `pirn_oilgas.seismic`

Seismic acquisition processing knots.

| Knot | Description |
|---|---|
| `SegyHeaderParser` | Parses and validates SEG-Y binary and trace headers |
| `CmpGatherExtractor` | Extracts Common-Midpoint (CMP) gathers from a sorted SEG-Y |
| `NmoCorrection` | Normal-moveout (NMO) correction |
| `StaticCorrection` | Datum and refraction static corrections |
| `VelocityAnalyzer` | Semblance-based velocity analysis |
| `StackProcessor` | CMP stack (fold sum / weighted stack) |
| `MigrationProcessor` | Kirchhoff post-stack migration |
| `HorizonPicker` | Auto-picking of seismic horizons |
| `FaultDetector` | 3D fault attribute computation |
| `SeismicAttributeCalculator` | Instantaneous amplitude, phase, frequency attributes |
| `FrequencyDecomposer` | Spectral decomposition (CWT / STFT) |
| `SubvolumeExtractor` | Extracts an inline/crossline/time sub-volume |

---

### `pirn_oilgas.well`

Well log and petrophysics knots.

| Knot | Description |
|---|---|
| `LasCurveValidator` | Validates LAS curve definitions against a reference dictionary |
| `DeviationSurveyProcessor` | Computes 3D well path from minimum-curvature deviation survey |
| `WellPathCalculator` | Calculates MD/TVD/THL/NS/EW from survey records |
| `FormationTopPicker` | Picks formation tops from gamma-ray / resistivity curves |
| `PorosityCalculator` | Computes total/effective porosity from density and neutron logs |
| `WaterSaturationCalculator` | Archie / Simandoux water saturation |
| `PermeabilityEstimator` | Permeability from NMR or empirical transforms |
| `LithologyClassifier` | Multi-log lithology classification |
| `LogNormalizer` | Cross-well log normalisation (histogram matching) |
| `PetrophysicalEvaluator` | Full petrophysical evaluation pipeline |
| `MudWeightCalculator` | Equivalent circulating density and mud weight optimisation |
| `CasingDesignEvaluator` | Casing seat selection and design pressure checks |
| `DirectionalDrillingPlanner` | Anti-collision and directional plan evaluation |

---

### `pirn_oilgas.reservoir`

Reservoir engineering and simulation knots.

| Knot | Description |
|---|---|
| `DeclineCurveAnalyzer` | Arps decline curve fitting (exponential/hyperbolic/harmonic) |
| `VolumetricEstimator` | OOIP / GIIP volumetric estimation |
| `MaterialBalanceCalculator` | Tank material balance (Havlena-Odeh) |
| `PvtTableProcessor` | Black-oil PVT table processing and correlation matching |
| `RelativePermeabilityModeler` | Corey/LET relative permeability curve fitting |
| `TypeCurveFitter` | Type-curve matching for unconventional reservoirs |
| `MonteCarloSimulator` | Probabilistic reserve estimation via Monte Carlo |
| `EclipseSmspecParser` | Parses Eclipse SMSPEC/UNSMRY simulation summary output |
| `CmgSsfileParser` | Parses CMG STARS/GEM simulation output files |

---

### `pirn_oilgas.production`

Production monitoring and optimisation knots.

| Knot | Description |
|---|---|
| `ProductionTestValidator` | Validates well test data against regulatory constraints |
| `GasOilRatioCalculator` | Computes GOR and condensate-gas ratio from production data |
| `WaterCutTracker` | Tracks water cut trends and breakthrough detection |
| `WaterInjectionTracker` | Injection allocation and voidage replacement analysis |
| `DeclineRateEstimator` | Rolling decline rate estimation from production history |
| `ProductionForecaster` | Production forecasting using decline curves or ML models |
| `FlowlinePressureModeler` | Simplified flowline pressure drop (Beggs-Brill) |
| `ArtificialLiftOptimizer` | ESP/rod-pump operating point optimisation |
| `WellTestAnalyzer` | Pressure transient analysis (Horner plot, skin, kh) |

---

### `pirn_oilgas.geospatial`

Geospatial and geodetic knots.

| Knot | Description |
|---|---|
| `CoordinateSystemTransformer` | Transforms well coordinates between CRS (via pyproj) |
| `WellLocationProjector` | Projects surface locations onto a survey grid |
| `FieldBoundaryDefiner` | Defines field boundaries from well header locations |
| `LeaseBlockGrouper` | Groups wells by government lease block |
| `BoundaryProximityChecker` | Checks well proximity to lease/regulatory boundaries |

---

### `pirn_oilgas.integrity`

Asset integrity and inspection knots.

| Knot | Description |
|---|---|
| `CorrosionRateEstimator` | Estimates corrosion rates from ILI and coupon data |
| `WallThicknessAnalyzer` | Remaining wall thickness analysis from UT/RT data |
| `PigRunDataProcessor` | Processes intelligent pig (ILI) inline inspection runs |
| `RiskBasedInspectionScorer` | API 581 risk-based inspection score calculation |
| `CathodicProtectionAnalyzer` | Cathodic protection effectiveness analysis |
| `EnergyEfficiencyKpiCalculator` | Energy intensity and GHG emission KPIs |

---

### `pirn_oilgas.workflows`

End-to-end `SubTapestry` workflows.

| Workflow | Description |
|---|---|
| `DeclineCurveReservesWorkflow` | Full reserves estimation: load production → fit decline → P10/P50/P90 reserves |
| `FieldProductionReportingWorkflow` | Field-level production reporting: ingest → aggregate → KPI → export |
| `SeismicToWellTieWorkflow` | Seismic-to-well tie: load SEG-Y + LAS → synthetic seismogram → cross-correlation |
| `WellborePetrophysicsWorkflow` | Full petrophysical evaluation: load LAS → QC → porosity → saturation → net-pay |

---

### `pirn_oilgas.protocols`

Connection interfaces for oilfield data systems.

| Class | Description |
|---|---|
| `HistorianConnection` | SCADA / OPC-DA historian connection interface |
| `SeismicVolumeStore` | Seismic volume storage interface (SEGY-SAP / in-house stores) |
| `WellDataService` | Well data service connection (OSDU / PPDM REST API) |

---

## Connector boundaries

All domain payload ingestion uses assembler knots — the ingestor pattern is abolished.

| Assembler | Input | Output |
|-----------|-------|--------|
| `LasObjectStoreAssembler` | `bytes` from object store | `LASPayload` |
| `SegyObjectStoreAssembler` | `bytes` from object store | `SegyVolume` |
| `ScadaDatabaseAssembler` | `list[tuple]` from database | `ScadaPayload` |
| `MudLogAssembler` | `bytes` | `dict[str, Any]` |
| `WellCompletionObjectStoreAssembler` | `bytes` | `DrillingParameters` |
| `LasObjectStoreDisassembler` | `LASPayload` | `bytes` |
| `SegyObjectStoreDisassembler` | `SegyVolume` | `bytes` |

All are in `pirn_oilgas/assemblers/` and `pirn_oilgas/disassemblers/`.

---

## Install Extras

```bash
pip install "pirn[oilgas]"
```

| Extra | Libraries installed | What it enables |
|---|---|---|
| `oilgas` | `segyio>=1.9`, `lasio>=0.31` | SEG-Y and LAS read/write; all oilgas sub-domain knots. WITSML, PRODML, RESQML, DLIS, SEG-D connectors also included (their dependencies — `defusedxml`, `dlisio` — are declared as transitive) |

Additional optional dependencies that are not automatically installed:

| Library | Install command | Enables |
|---|---|---|
| `dlisio` | `pip install dlisio` | `DlisFormat` decode |
| `segpy` | `pip install segpy` | Improved `SegdFormat` decode (falls back to pure-Python otherwise) |
| `pyproj` | `pip install pyproj` | `CoordinateSystemTransformer` (geospatial sub-domain) |
| `pyspark` | `pip install pirn[spark]` | Spark-backed distributed processing for large seismic volumes |

**See also:** [Signal Domain — Spectral Analysis](signal.md#pirndomainssignalspectral), [File Formats — Connectors](../connectors/index.md), [Backends](../guides/backends.md)
