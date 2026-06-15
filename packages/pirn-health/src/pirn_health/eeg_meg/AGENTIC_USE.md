Processes EEG and MEG signals — artifact removal, montage application, frequency analysis, epoching, and source localisation — does NOT read EDF, BDF, or BrainVision files; use EdfFormat, EdfPlusFormat, BdfFormat, or BrainVisionFormat from the file_formats connector layer.

## Mental model

EEG/MEG knots operate on MNE `Raw`, `Epochs`, or `Evoked` objects passed as serialised bytes or in-memory representations. The standard processing chain is: apply montage → notch filter (line noise) → bandpass filter → ICA artifact removal → epoch extraction → frequency or source analysis.

Knots wrap MNE operations. Each knot accepts the previous MNE object and returns a transformed one, allowing you to compose the full preprocessing pipeline as a pirn `Tapestry` without managing intermediate MNE state manually.

The `MriQcGate` knot is MRI-specific; EEG/MEG quality control is handled via signal-level checks within `ArtifactRemover` and `EegIcaDecomposer`. Both raise `ValueError` with descriptive messages when channel counts, sampling rates, or component thresholds fall outside expected ranges.

## Source map

```
pirn_health/eeg_meg/
├── artifact_remover.py                  ArtifactRemover                  — detects and interpolates bad channels and epochs
├── bandpass_filter.py                   EegBandpassFilter                   — zero-phase FIR bandpass filter (cutoff configurable)
├── coherence_analyzer.py                CoherenceAnalyzer                — inter-channel magnitude-squared coherence
├── connectivity_analyzer.py             ConnectivityAnalyzer             — spectral connectivity (PLI, PLV, dwPLI) via MNE-Connectivity
├── eeg_ica_decomposer.py                EegIcaDecomposer                 — FastICA/Infomax decomposition and artifact component rejection
├── eeg_montage_applier.py               EegMontageApplier                — applies standard or custom electrode montage
├── epoch_extractor.py                   EpochExtractor                   — extracts epochs around events with configurable window
├── evoked_response_averager.py          EvokedResponseAverager           — averages epochs to produce evoked response
├── meg_beamformer.py                    MegBeamformer                    — LCMV/DICS beamformer spatial filter for MEG source imaging
├── notch_filter.py                      EegNotchFilter                      — notch filter for line-noise removal (50/60 Hz)
├── power_spectral_density_estimator.py  PowerSpectralDensityEstimator    — Welch/multitaper PSD estimation per channel
├── source_localizer.py                  SourceLocalizer                  — EEG/MEG dipole fitting and distributed source localisation
└── time_frequency_decomposer.py         TimeFrequencyDecomposer          — Morlet wavelet or multitaper TFR decomposition
```

## Canonical pattern

EDF bytes (decoded by connector) → montage apply → notch filter → bandpass → ICA artifact removal → epoch extract → PSD:

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn_health.eeg_meg.eeg_montage_applier import EegMontageApplier
from pirn_health.eeg_meg.eeg_notch_filter import EegNotchFilter
from pirn_health.eeg_meg.eeg_bandpass_filter import EegBandpassFilter
from pirn_health.eeg_meg.eeg_ica_decomposer import EegIcaDecomposer
from pirn_health.eeg_meg.epoch_extractor import EpochExtractor
from pirn_health.eeg_meg.power_spectral_density_estimator import PowerSpectralDensityEstimator
from pirn.tapestry import Tapestry

# raw_signal is an MNE Raw object produced by EdfFormat.decode() upstream
with Tapestry() as t:
    raw_signal = Parameter("raw_signal", object)  # MNE Raw
    events     = Parameter("events", object)       # MNE events array

    montaged = EegMontageApplier(
        raw=raw_signal,
        montage="standard_1020",
        _config=KnotConfig(id="montage"),
    )
    notched = EegNotchFilter(
        raw=montaged,
        freqs=[50.0, 100.0],
        _config=KnotConfig(id="notch"),
    )
    bandpassed = EegBandpassFilter(
        raw=notched,
        l_freq=1.0,
        h_freq=40.0,
        _config=KnotConfig(id="bandpass"),
    )
    cleaned = EegIcaDecomposer(
        raw=bandpassed,
        _config=KnotConfig(id="ica"),
    )
    epochs = EpochExtractor(
        raw=cleaned,
        events=events,
        tmin=-0.2,
        tmax=0.8,
        _config=KnotConfig(id="epochs"),
    )
    PowerSpectralDensityEstimator(
        epochs=epochs,
        fmin=1.0,
        fmax=40.0,
        _config=KnotConfig(id="psd"),
    )

result = await t.run(RunRequest(parameters={
    "raw_signal": mne_raw_object,
    "events": mne_events_array,
}))
psd = result.outputs["psd"]
```

## Anti-patterns

**Applying ICA before filtering** — `EegIcaDecomposer` expects a bandpass-filtered signal. Running ICA on broadband or line-noise-contaminated data inflates component count and makes artifact components harder to identify. Always apply `EegNotchFilter` and `EegBandpassFilter` before `EegIcaDecomposer`.

**Running `SourceLocalizer` without a forward model** — `SourceLocalizer` and `MegBeamformer` require a precomputed forward solution (leadfield matrix). They do not compute the forward model internally. Provide the forward solution path via `KnotConfig.extra`; omitting it raises `RuntimeError` at process time.

**Ignoring sampling-rate mismatches between knots** — several knots (e.g., `TimeFrequencyDecomposer`) assume the sampling rate set in the MNE object metadata is consistent with the data array. If you manually resample data outside of pirn and pass the result back in, update the MNE `info["sfreq"]` accordingly or downstream frequency estimates will be wrong.

## Constraints and gotchas

- All knots depend on MNE-Python (`mne>=1.6`). MNE is not imported at package load time; `process()` will fail if `mne` is not installed.
- `MegBeamformer` and `SourceLocalizer` additionally require `mne-connectivity` and a valid MRI/BEM forward model; see MNE documentation for forward model construction.
- `EegIcaDecomposer` is non-deterministic by default. Set `random_state` in `KnotConfig.extra` for reproducible component decomposition.
- `CoherenceAnalyzer` and `ConnectivityAnalyzer` operate on `Epochs` objects, not `Raw`. Wire `EpochExtractor` before either connectivity knot.
- `ArtifactRemover` interpolates bad channels in place. If no bad channels are detected it returns the signal unchanged — this is not an error.
- Install: `pip install pirn[eeg]`

## Quick reference

| Task | How |
|---|---|
| Decode EDF/BDF/BrainVision bytes | `EdfFormat` / `BdfFormat` / `BrainVisionFormat` (connector layer) |
| Apply electrode montage | `EegMontageApplier` |
| Remove line noise | `EegNotchFilter` (50 or 60 Hz) |
| Bandpass for ERP | `EegBandpassFilter` (1–40 Hz typical) |
| Remove ocular/muscle artifacts | `EegIcaDecomposer` |
| Extract event-locked epochs | `EpochExtractor` |
| Compute ERP | `EvokedResponseAverager` on epochs |
| Per-channel PSD | `PowerSpectralDensityEstimator` |
| Time-frequency decomposition | `TimeFrequencyDecomposer` (Morlet wavelets) |
| Source localisation | `SourceLocalizer` (EEG) or `MegBeamformer` (MEG) |
| Spectral connectivity | `CoherenceAnalyzer` or `ConnectivityAnalyzer` |

*See also: [health AGENTIC_USE.md](../AGENTIC_USE.md)*
