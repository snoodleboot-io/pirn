Audio signal processing — denoise, extract features, estimate pitch, detect beats, and augment audio waveforms.

## Mental model

Knots here operate on audio waveforms (1-D float arrays, mono or stereo) at a known `fs`. They span the pipeline from raw waveform to high-level descriptors (MFCCs, beat positions, speaker segments). File I/O is deliberately out of scope — load audio through `pirn.connectors.file_formats` using `WavFormat` or `Mp3Format` before wiring into these knots. Resampling to a target rate before feature extraction should go through `pirn.domains.signal.resampling.AudioResampler` (or the dedicated `AudioResampler` here which wraps it for audio conventions).

## Source map

```
├── audio_augmentation_pipeline.py  AudioAugmentationPipeline  — applies random pitch/tempo/noise augmentations
├── audio_denoiser.py               AudioDenoiser              — spectral subtraction or Wiener denoising
├── audio_feature_extractor.py      AudioFeatureExtractor      — extracts RMS, ZCR, spectral centroid, etc.
├── audio_resampler.py              AudioResampler             — converts audio to a target sample rate
├── beat_tracker.py                 BeatTracker                — estimates beat positions and tempo (BPM)
├── mel_spectrogram_extractor.py    MelSpectrogramExtractor    — mel-scaled log spectrogram (freq × time)
├── mfcc_extractor.py               MfccExtractor              — mel-frequency cepstral coefficients
├── music_information_retriever.py  MusicInformationRetriever  — key, mode, chroma, and tonal features
├── onset_detector.py               OnsetDetector              — detects note/transient onsets
├── pitch_estimator.py              PitchEstimator             — fundamental frequency (F0) estimation
├── speaker_diarization_pipeline.py SpeakerDiarizationPipeline — segments audio by speaker identity
├── vad_detector.py                 VadDetector                — voice activity detection (speech vs. silence)
└── (AudioResampler wraps resampling/ for audio-idiomatic use)
```

## Canonical pattern

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn.domains.signal.audio.audio_denoiser import AudioDenoiser
from pirn.domains.signal.audio.mfcc_extractor import MfccExtractor

tapestry = Tapestry()

denoised = AudioDenoiser(
    signal=Parameter("raw_audio"),
    fs=16000,
    method="wiener",
    _config=KnotConfig(id="denoised"),
)
mfccs = MfccExtractor(
    signal=denoised.output,
    fs=16000,
    n_mfcc=13,
    n_mels=40,
    _config=KnotConfig(id="mfccs"),
)

result = tapestry.run(RunRequest(inputs={"raw_audio": waveform}))
features = result["mfccs"]  # shape: (n_mfcc, time_frames)
```

## Anti-patterns

- **Loading audio files inside audio knots.** These knots expect a waveform array. Use `pirn.connectors.file_formats.WavFormat` / `Mp3Format` upstream.
- **Skipping resampling when `fs` mismatches.** Passing a 44100 Hz signal to a knot configured for 16000 Hz will silently produce wrong feature timings; always resample first.
- **Running `SpeakerDiarizationPipeline` on short clips.** Diarization needs at least several seconds per speaker to converge reliably; pad or segment long recordings.

## Constraints and gotchas

- `MelSpectrogramExtractor` and `MfccExtractor` expect mono audio; average stereo channels before wiring in.
- `AudioAugmentationPipeline` is stochastic — set a random seed via `KnotConfig` metadata if reproducibility matters.
- `BeatTracker` assumes music; it will produce spurious results on speech or noise-only signals.
- `VadDetector` outputs a boolean mask array aligned with the input waveform, not a list of timestamps; convert with `np.where` if timestamps are needed.
- `PitchEstimator` is undefined for polyphonic signals — use for single-instrument or speech only.
- Extra: `pirn[signal-audio]` (installs librosa and related deps).

## Quick reference

| Goal | Knot |
|---|---|
| Reduce background noise | `AudioDenoiser` |
| Speech features (ASR) | `MfccExtractor` |
| Music/CNN features | `MelSpectrogramExtractor` |
| Tempo and beat grid | `BeatTracker` |
| Speech segments | `VadDetector` |
| Speaker turn detection | `SpeakerDiarizationPipeline` |
| Transient / onset times | `OnsetDetector` |
| Data augmentation | `AudioAugmentationPipeline` |
| Convert sample rate | `AudioResampler` |

---

*See also: [signal AGENTIC_USE.md](../AGENTIC_USE.md)*
