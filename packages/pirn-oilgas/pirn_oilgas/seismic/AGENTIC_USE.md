Processes seismic data — gather conditioning, velocity analysis, migration, attribute extraction, and acoustic impedance inversion. Does NOT read SEG-Y or SEG-D files; use SegyFormat/SegdFormat from file_formats.

## Mental model

A seismic processing pipeline is a directed graph of transform knots, each consuming and emitting trace arrays or attribute volumes. Gathers move through conditioning (gain, mute, decon) before velocity analysis and stacking, then migration repositions reflectors to true subsurface locations. Attribute and inversion knots operate on migrated data to derive rock-property proxies.

## Source map

```
├── acoustic_impedance_inverter.py    AcousticImpedanceInverter    — model-based post-stack acoustic impedance inversion
├── cmp_gather_extractor.py           CmpGatherExtractor           — sorts input trace data into CMP gathers
├── fault_detector.py                 FaultDetector                — detects faults from coherence or similarity volumes
├── fk_denoising_knot.py              FKDenoisingKnot              — applies F-K domain noise suppression
├── frequency_decomposer.py           FrequencyDecomposer          — spectral decomposition into sub-bands
├── horizon_picker.py                 HorizonPicker                — picks seismic horizons from amplitude volumes
├── instantaneous_attribute_extractor.py  InstantaneousAttributeExtractor  — computes instantaneous phase, amplitude, and frequency
├── migration_processor.py            MigrationProcessor           — applies Kirchhoff or phase-shift migration
├── mute_applicator.py                MuteApplicator               — applies top, surgical, or surgical mute functions
├── nmo_correction.py                 NmoCorrection                — applies NMO correction using a velocity model
├── seismic_qc_check.py               SeismicQCCheck               — checks trace health, fold, and S/N thresholds before downstream steps
├── spectral_whitener.py              SpectralWhitener             — flattens amplitude spectrum within an operator length
├── surface_consistent_deconvolver.py SurfaceConsistentDeconvolver — surface-consistent spiking or predictive deconvolution
├── stacking_velocity_picker.py       StackingVelocityPicker       — semblance-based stacking velocity picker
├── time_depth_converter.py           TimeDepthConverter           — converts two-way time volumes to depth using a velocity model
├── trace_gain_applier.py             TraceGainApplier             — applies time-variant gain (AGC, spherical divergence, etc.)
├── velocity_model_builder.py         VelocityModelBuilder         — assembles interval velocity models from picked velocities
├── wavelet_extractor.py              WaveletExtractor             — statistical or well-tie wavelet extraction
├── zero_phasing_operator.py          ZeroPhasingOperator          — rotates data to zero phase using an extracted wavelet
```

## Canonical pattern

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_oilgas.seismic.cmp_gather_extractor import CmpGatherExtractor
from pirn_oilgas.seismic.nmo_correction import NmoCorrection
from pirn_oilgas.seismic.migration_processor import MigrationProcessor
from pirn_oilgas.seismic.instantaneous_attribute_extractor import (
    InstantaneousAttributeExtractor,
)
from pirn_oilgas.seismic.seismic_qc_check import SeismicQCCheck

with Tapestry() as t:
    raw_traces = Parameter("raw_traces", object)  # trace array from SegyFormat

    gathers = CmpGatherExtractor(
        traces=raw_traces,
        _config=KnotConfig(id="cmp_extract"),
    )

    qc_passed = SeismicQCCheck(
        gathers=gathers,
        _config=KnotConfig(id="seismic_qc"),
    )

    nmo = NmoCorrection(
        gather=qc_passed,
        stacking_velocity_m_s=1500.0,
        _config=KnotConfig(id="nmo"),
    )

    migrated = MigrationProcessor(
        stack=nmo,
        _config=KnotConfig(id="migration", params={"algorithm": "kirchhoff"}),
    )

    attributes = InstantaneousAttributeExtractor(
        volume=migrated,
        _config=KnotConfig(id="attr_extract", params={"attributes": ["phase", "amplitude"]}),
    )

result = await t.run(RunRequest(parameters={"raw_traces": trace_array}))
```

## Anti-patterns

**Skipping SeismicQCCheck before velocity analysis** — feeding unchecked gathers into StackingVelocityPicker propagates dead traces and noisy semblance panels silently.

**Running MigrationProcessor on time-domain gathers instead of a stack** — migration expects a stacked or angle-stacked volume; passing pre-stack gathers without explicit pre-stack migration config produces smeared output.

**Chaining TimeDepthConverter before VelocityModelBuilder** — the converter depends on a complete interval velocity model; building the model in a separate upstream step is required.

## Constraints and gotchas

- `SeismicQCCheck` raises `KnotCheckError` when fold drops below the configured threshold; set `min_fold` explicitly for sparse 3D surveys.
- `NmoCorrection` expects `stacking_velocity_m_s` in m/s; ft/s inputs will produce silent stretch artefacts without unit conversion.
- `AcousticImpedanceInverter` requires a low-frequency model parameter; omitting it defaults to zero LF trend, which biases absolute impedance.
- `MigrationProcessor` with `algorithm="phase_shift"` loads the full velocity field into memory; use `algorithm="kirchhoff"` for large 3D volumes.
- Install extra: `pip install pirn[seismic]`

## Quick reference

| Task | How |
|------|-----|
| Extract CMP gathers from trace array | `CmpGatherExtractor(traces=param)` |
| Validate gather health before processing | `SeismicQCCheck(gathers=gathers)` |
| Apply NMO and stack gathers | `NmoCorrection` then sum in `MigrationProcessor` |
| Pick stacking velocities from semblance | `StackingVelocityPicker(gathers=gathers)` |
| Build velocity model from picks | `VelocityModelBuilder(picks=picks)` |
| Convert time volume to depth | `TimeDepthConverter(volume=migrated, velocity_model=vm)` |
| Extract instantaneous attributes | `InstantaneousAttributeExtractor(volume=migrated)` |
| Invert for acoustic impedance | `AcousticImpedanceInverter(stack=migrated, wavelet=wavelet)` |
| Pick horizons on amplitude volume | `HorizonPicker(volume=migrated)` |
| Detect faults from coherence | `FaultDetector(coherence_volume=coherence)` |

*See also: [oilgas AGENTIC_USE.md](../AGENTIC_USE.md)*
