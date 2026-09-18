Processes seismic data — gather conditioning, velocity analysis, stacking, migration, attribute extraction, and acoustic impedance inversion. Does NOT read SEG-Y or SEG-D files; use `SegyFormat` / `SegdFormat` from `pirn.connectors.file_formats`.

## Mental model

A seismic processing pipeline is a directed graph of transform knots. Most of them take and return a `SegyVolume` (`pirn_oilgas.types.segy_volume`) — a typed *reference* carrying `volume_id` and the inline / xline / sample counts, not the sample buffer itself. Gathers move through conditioning (statics, gain, bandpass, F-K denoise) before velocity analysis and stacking, then migration repositions reflectors to their true subsurface locations. Attribute and inversion knots operate on migrated data to derive rock-property proxies.

Every knot here is imported from the module that defines it. `pirn_oilgas/seismic/__init__.py` re-exports nothing (`__all__` is empty) — the house convention forbids import forwarding — so importing a class straight from the `pirn_oilgas.seismic` package raises `ImportError`.

## Source map

```
├── acoustic_impedance_inverter.py        AcousticImpedanceInverter       — model-based inversion for acoustic impedance from amplitudes
├── cmp_gather_extractor.py               CmpGatherExtractor              — extracts a CMP gather from a 3-D SegyVolume
├── fault_detector.py                     FaultDetector                   — thresholds a coherence / discontinuity attribute to highlight faults
├── fk_denoising_knot.py                  FKDenoisingKnot                 — attenuates coherent noise in the frequency-wavenumber domain
├── frequency_decomposer.py               FrequencyDecomposer             — decomposes a volume into a configured set of frequency bands
├── horizon_picker.py                     HorizonPicker                   — auto-picks a horizon from a seed inline / xline
├── instantaneous_attribute_extractor.py  InstantaneousAttributeExtractor — instantaneous amplitude / phase / frequency via Hilbert transform
├── migration_processor.py                MigrationProcessor              — migrates a volume (kirchhoff, rtm, phase_shift, stolt)
├── nmo_correction.py                     NmoCorrection                   — NMO-corrects a CMP gather with a supplied stacking velocity
├── rms_amplitude_window_extractor.py     RMSAmplitudeWindowExtractor     — RMS amplitude map in a window around a picked horizon
├── segy_header_parser.py                 SegyHeaderParser                — parses a representative trace header from the volume
├── seismic_attribute_calculator.py       SeismicAttributeCalculator      — computes a single attribute volume (envelope, instantaneous freq, …)
├── seismic_bandpass_filter.py            SeismicBandpassFilter           — trapezoidal (Ormsby) bandpass filter over trace data
├── seismic_qc_check.py                   SeismicQCCheck                  — fold / null-percentage / amplitude gate; raises on violation
├── spherical_divergence_gain.py          SphericalDivergenceGain         — corrects amplitudes for geometric spreading
├── stack_processor.py                    StackProcessor                  — stacks a corrected CMP gather to a single trace volume
├── static_correction.py                  StaticCorrection                — applies elevation / weathering statics
├── subvolume_extractor.py                SubvolumeExtractor              — extracts a 3-D sub-cube from a parent volume
├── velocity_analyzer.py                  VelocityAnalyzer                — picks a stacking velocity (m/s) from a CMP gather by semblance
└── velocity_model_builder.py             VelocityModelBuilder            — interpolates a 3-D velocity model from semblance picks and well velocities
```

## Canonical pattern

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_oilgas.seismic.cmp_gather_extractor import CmpGatherExtractor
from pirn_oilgas.seismic.instantaneous_attribute_extractor import InstantaneousAttributeExtractor
from pirn_oilgas.seismic.migration_processor import MigrationProcessor
from pirn_oilgas.seismic.nmo_correction import NmoCorrection
from pirn_oilgas.seismic.seismic_qc_check import SeismicQCCheck
from pirn_oilgas.seismic.stack_processor import StackProcessor
from pirn_oilgas.seismic.velocity_analyzer import VelocityAnalyzer
from pirn_oilgas.types.segy_volume import SegyVolume

with Tapestry() as t:
    survey = Parameter("survey", SegyVolume, _config=KnotConfig(id="survey"))
    trace_stats = Parameter("trace_stats", dict, _config=KnotConfig(id="trace_stats"))

    SeismicQCCheck(
        data=trace_stats,
        max_null_pct=5.0,
        min_fold=24,
        max_amplitude=1.0e6,
        _config=KnotConfig(id="seismic_qc"),
    )

    gather = CmpGatherExtractor(
        volume=survey,
        cmp_inline=250,
        cmp_xline=480,
        _config=KnotConfig(id="cmp_extract"),
    )

    velocity = VelocityAnalyzer(
        gather=gather,
        initial_velocity_m_s=2400.0,
        _config=KnotConfig(id="vel_pick"),
    )

    corrected = NmoCorrection(
        gather=gather,
        stacking_velocity_m_s=velocity,
        _config=KnotConfig(id="nmo"),
    )

    stack = StackProcessor(gather=corrected, _config=KnotConfig(id="stack"))

    migrated = MigrationProcessor(
        volume=stack,
        method="kirchhoff",
        _config=KnotConfig(id="migration"),
    )

    attributes = InstantaneousAttributeExtractor(
        trace=trace_stats,
        attributes=("amplitude", "phase"),
        _config=KnotConfig(id="attr_extract"),
    )

result = await t.run(
    RunRequest(parameters={"survey": survey_ref, "trace_stats": stats_dict})
)
```

## Anti-patterns

**Importing from the sub-package** — naming a class on the `pirn_oilgas.seismic` package itself (rather than on `pirn_oilgas.seismic.cmp_gather_extractor`) raises `ImportError`; the `__init__.py` deliberately re-exports nothing. Import from the defining module instead.

**Stacking before NMO** — `StackProcessor` sums the gather as given; feeding it a gather that has not been through `NmoCorrection` destroys the reflection alignment the stack relies on.

**Hard-coding a stacking velocity into `NmoCorrection`** — `VelocityAnalyzer` returns the picked velocity as a plain `float` knot output; wire it into `stacking_velocity_m_s` so the pick is captured in lineage instead of a magic number.

**Feeding `InstantaneousAttributeExtractor` a `SegyVolume`** — it takes `trace` as a `dict[str, Any]` of trace samples, not a volume reference; a migrated `SegyVolume` has to be sampled into a trace dict first.

## Constraints and gotchas

- `SeismicQCCheck` raises `ValueError` when `fold` is below `min_fold` or the null percentage exceeds `max_null_pct`; it reads `data["fold"]` and `data["traces"]`, and returns `{"passed", "trace_count", "issues"}` when everything passes. `min_fold`, `max_null_pct` and `max_amplitude` are required — there are no defaults.
- `MigrationProcessor.method` must be one of `kirchhoff`, `rtm`, `phase_shift`, `stolt`; anything else raises `ValueError`.
- `VelocityModelBuilder.interpolation_method` must be one of `idw`, `kriging`, `natural_neighbor`.
- Velocities are metres per second throughout (`stacking_velocity_m_s`, `initial_velocity_m_s`, `velocity_threshold_m_s`); there is no unit metadata, so ft/s inputs corrupt results silently.
- `AcousticImpedanceInverter` requires `low_frequency_model` as a knot input — it has no default; `regularization` defaults to `0.0`.
- Install extra: `pip install "pirn-oilgas[oilgas]"` (pulls `segyio`, `scipy`, `resfo`, `lasio`).

## Quick reference

| Task | How |
|------|-----|
| Gate data on fold / nulls / amplitude | `SeismicQCCheck(data=stats, max_null_pct=5.0, min_fold=24, max_amplitude=1e6, _config=...)` |
| Extract a CMP gather from a volume | `CmpGatherExtractor(volume=survey, cmp_inline=250, cmp_xline=480, _config=...)` |
| Pick a stacking velocity | `VelocityAnalyzer(gather=gather, initial_velocity_m_s=2400.0, _config=...)` |
| Apply NMO | `NmoCorrection(gather=gather, stacking_velocity_m_s=velocity, _config=...)` |
| Stack a corrected gather | `StackProcessor(gather=corrected, _config=...)` |
| Migrate a volume | `MigrationProcessor(volume=stack, method="kirchhoff", _config=...)` |
| Apply elevation statics | `StaticCorrection(gather=gather, datum_elevation_m=..., replacement_velocity_m_s=..., _config=...)` |
| Correct geometric spreading | `SphericalDivergenceGain(data=gather, velocity_m_s=2400.0, t_power=2.0, _config=...)` |
| Bandpass filter traces | `SeismicBandpassFilter(data=gather, low_cut_hz=..., low_pass_hz=..., high_pass_hz=..., high_cut_hz=..., _config=...)` |
| Suppress coherent noise (F-K) | `FKDenoisingKnot(gather=gather, velocity_threshold_m_s=..., taper_width_pct=..., _config=...)` |
| Build a velocity model | `VelocityModelBuilder(semblance_picks=picks, well_velocities=wells, interpolation_method="kriging", _config=...)` |
| Extract instantaneous attributes | `InstantaneousAttributeExtractor(trace=trace_dict, attributes=("amplitude", "phase"), _config=...)` |
| Compute one attribute volume | `SeismicAttributeCalculator(volume=migrated, attribute="envelope", _config=...)` |
| Spectral decomposition | `FrequencyDecomposer(volume=migrated, center_frequencies_hz=(15.0, 30.0, 45.0), _config=...)` |
| Pick a horizon | `HorizonPicker(volume=migrated, horizon_name="Top_Res", seed_inline=250, seed_xline=480, _config=...)` |
| RMS amplitude around a horizon | `RMSAmplitudeWindowExtractor(volume=migrated, horizon=horizon, window_ms_above=20.0, window_ms_below=20.0, _config=...)` |
| Detect faults from coherence | `FaultDetector(attribute_volume=coherence, coherence_threshold=0.6, _config=...)` |
| Invert for acoustic impedance | `AcousticImpedanceInverter(seismic_volume=migrated, wavelet=wavelet, low_frequency_model=lfm, _config=...)` |
| Extract a sub-cube | `SubvolumeExtractor(volume=survey, inline_start=..., inline_end=..., xline_start=..., xline_end=..., sample_start=..., sample_end=..., _config=...)` |
| Read a representative trace header | `SegyHeaderParser(volume=survey, _config=...)` |

*See also: [oilgas AGENTIC_USE.md](../AGENTIC_USE.md)*
