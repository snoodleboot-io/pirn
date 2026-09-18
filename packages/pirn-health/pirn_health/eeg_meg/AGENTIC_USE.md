Processes EEG and MEG signals — filtering, artifact removal, montage application, frequency analysis, epoching, and source localisation — does NOT read EDF, BDF, or BrainVision files; use EdfFormat, EdfPlusFormat, BdfFormat, or BrainVisionFormat from the file_formats connector layer.

## Mental model

Most EEG/MEG knots take a `HealthSignalPayload` (`pirn_health.types.health_signal_payload`): a `HealthSignalFrame` metadata object (signal id, channel count, sample rate, samples per channel) bundled with a NumPy sample array shaped `(channels, samples)`. Filters and `ArtifactRemover` return a new `HealthSignalPayload`, so they chain directly; analysis knots return plain mappings (band powers, coherence per channel pair, seizure intervals). `EegObjectStoreAssembler` in `pirn_health.assemblers` builds a `HealthSignalPayload` from raw EEG bytes.

The typical processing chain is: notch filter (line noise) → bandpass filter → artifact removal → epoch extraction or frequency analysis.

Computation uses SciPy and scikit-learn (the `health` extra). Knots validate their inputs and raise `TypeError`/`ValueError` with descriptive messages on a wrong payload type, non-positive frequency, or invalid method name.

## Source map

```
pirn_health/eeg_meg/
├── artifact_remover.py           ArtifactRemover         — ICA (FastICA) decomposition and reconstruction of the signal
├── coherence_analyzer.py         CoherenceAnalyzer       — magnitude-squared coherence between channel pairs over a band
├── connectivity_analyzer.py      ConnectivityAnalyzer    — pairwise phase-locking value between channels
├── eeg_bandpass_filter.py        EegBandpassFilter       — zero-phase Butterworth bandpass filter
├── eeg_ica_decomposer.py         EEGICADecomposer        — ICA mixing/unmixing matrices and component variances
├── eeg_montage_applier.py        EEGMontageApplier       — re-reference, drop channels, set channel positions
├── eeg_notch_filter.py           EegNotchFilter          — notch filter for line-noise removal (50/60 Hz)
├── epoch_extractor.py            EpochExtractor          — event-locked epochs as a tuple of payloads
├── evoked_response_averager.py   EvokedResponseAverager  — averages epochs into an evoked response
├── meg_beamformer.py             MEGBeamformer           — LCMV beamformer for a given steering vector
├── power_spectrum_estimator.py   PowerSpectrumEstimator  — Welch PSD integrated into delta/theta/alpha/beta/gamma band power
├── seizure_detector.py           SeizureDetector         — RMS-threshold seizure interval detection
├── sleep_stage_classifier.py     SleepStageClassifier    — 30 s epoch sleep staging (W, N1, N2, N3, REM)
├── source_localizer.py           SourceLocalizer         — minimum-norm-style source activation estimates
└── time_frequency_decomposer.py  TimeFrequencyDecomposer — Morlet wavelet power per frequency
```

## Canonical pattern

Decoded signal payload → notch filter → bandpass → artifact removal → band power, plus an evoked-response branch:

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_health.eeg_meg.artifact_remover import ArtifactRemover
from pirn_health.eeg_meg.eeg_bandpass_filter import EegBandpassFilter
from pirn_health.eeg_meg.eeg_notch_filter import EegNotchFilter
from pirn_health.eeg_meg.epoch_extractor import EpochExtractor
from pirn_health.eeg_meg.evoked_response_averager import EvokedResponseAverager
from pirn_health.eeg_meg.power_spectrum_estimator import PowerSpectrumEstimator
from pirn_health.types.health_signal_payload import HealthSignalPayload

with Tapestry() as t:
    raw_signal = Parameter("raw_signal", HealthSignalPayload)
    event_times = Parameter("event_times", list[float])

    notched = EegNotchFilter(
        signal=raw_signal,
        notch_hz=50.0,
        _config=KnotConfig(id="notch"),
    )
    bandpassed = EegBandpassFilter(
        signal=notched,
        low_hz=1.0,
        high_hz=40.0,
        _config=KnotConfig(id="bandpass"),
    )
    cleaned = ArtifactRemover(
        signal=bandpassed,
        n_components=16,
        method="fastica",
        _config=KnotConfig(id="ica"),
    )
    PowerSpectrumEstimator(
        signal=cleaned,
        method="welch",
        _config=KnotConfig(id="band_power"),
    )
    epochs = EpochExtractor(
        signal=cleaned,
        event_times_sec=event_times,
        tmin_sec=-0.2,
        tmax_sec=0.8,
        _config=KnotConfig(id="epochs"),
    )
    EvokedResponseAverager(
        epochs=epochs,
        condition="target",
        _config=KnotConfig(id="erp"),
    )

result = await t.run(RunRequest(parameters={
    "raw_signal": signal_payload,
    "event_times": [12.4, 15.9, 21.3],
}))
band_power = result.outputs["band_power"]
```

## Anti-patterns

**Running ICA before filtering** — `ArtifactRemover` and `EEGICADecomposer` expect a notch- and bandpass-filtered signal. ICA on broadband or line-noise-contaminated data spends components on drift and mains noise. Apply `EegNotchFilter` and `EegBandpassFilter` first.

**Treating `EEGMontageApplier` or `EEGICADecomposer` output as a signal payload** — both return plain dicts (montage metadata; mixing/unmixing matrices), not `HealthSignalPayload`. They cannot be wired into a knot whose input is `signal`.

**Ignoring the sample rate** — every frequency computation reads `sample_rate_hz` from the payload's `HealthSignalFrame`. If you resample data outside pirn, build a new frame with the new rate or downstream frequency estimates will be wrong.

## Constraints and gotchas

- `PowerSpectrumEstimator` computes band power on the first channel only (or the mono signal).
- `ArtifactRemover` reconstructs the signal from all components; it does not identify or drop artifact components (that requires expert labels).
- `SleepStageClassifier` only accepts `epoch_duration_sec=30` and uses heuristic band-power thresholds.
- `MEGBeamformer` requires the `steering_vector` length to match the channel count; `SourceLocalizer` does not take a forward model and returns a simplified minimum-norm estimate per source label.
- `EvokedResponseAverager` takes the tuple of payloads returned by `EpochExtractor`; `CoherenceAnalyzer`, `ConnectivityAnalyzer`, and `TimeFrequencyDecomposer` take a single `HealthSignalPayload`.
- Install: `pip install "pirn-health[health]"`

## Quick reference

| Task | How |
|---|---|
| Decode EDF/BDF/BrainVision bytes | `EdfFormat` / `BdfFormat` / `BrainVisionFormat` (connector layer) |
| Build a signal payload from stored bytes | `EegObjectStoreAssembler` |
| Apply electrode montage | `EEGMontageApplier` |
| Remove line noise | `EegNotchFilter` (50 or 60 Hz) |
| Bandpass for ERP | `EegBandpassFilter` (1–40 Hz typical) |
| ICA artifact pass | `ArtifactRemover` (signal out) or `EEGICADecomposer` (matrices out) |
| Extract event-locked epochs | `EpochExtractor` |
| Compute ERP | `EvokedResponseAverager` on epochs |
| Band power | `PowerSpectrumEstimator` |
| Time-frequency decomposition | `TimeFrequencyDecomposer` (Morlet wavelets) |
| Source localisation | `SourceLocalizer` (EEG) or `MEGBeamformer` (MEG) |
| Channel connectivity | `CoherenceAnalyzer` or `ConnectivityAnalyzer` |
| Seizure detection / sleep staging | `SeizureDetector` / `SleepStageClassifier` |

*See also: [health AGENTIC_USE.md](../AGENTIC_USE.md)*
