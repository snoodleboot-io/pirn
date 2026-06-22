# AGENTIC_USE — pirn_signal

> This domain provides async, typed DSP pipeline knots for filtering, spectral analysis, wavelets, resampling, adaptive filters, source separation, nonlinear dynamics, and audio feature extraction; it does NOT include biosignal formats (see the health domain) or raw audio file connectors (see `pirn.connectors.file_formats`).

---

## Mental model

Every knot in this domain consumes a **`SignalFrame`** and emits either another `SignalFrame` or a specialised output frame (`SpectrumFrame`, `WaveletFrame`, `SourceFrame`). A `SignalFrame` is a lightweight metadata reference — it carries `signal_id`, `channel_count`, `sample_rate_hz`, `samples_per_channel`, and a `fetched_at` timestamp, but does **not** embed sample arrays. Samples are loaded on demand at execution time by the concrete backend (scipy / pywavelets / librosa).

Sub-areas and their roles in a typical DSP pipeline:

```
Raw audio bytes arrive via an `ObjectStoreReadSource` connector and enter the domain through `SignalObjectStoreAssembler`.
    ↓
resampling          — normalise sample rate before any processing
    ↓
filters             — remove noise, isolate bands
    ↓
spectral / wavelets — frequency-domain or time-frequency analysis
    ↓
adaptive / separation / nonlinear / statistical — advanced estimation
    ↓
audio               — high-level MIR features (music/speech)
```

Knots compose by passing the upstream knot as the `signal=` argument of the downstream knot. pirn resolves the DAG at run time; no data flows at construction time.

---

## Install

```bash
pip install "pirn-signal[signal]"
```

`pirn-signal[signal]` pulls in `scipy>=1.12`, `pywavelets>=1.5`, and `librosa>=0.10`.

Audio file connectors (WAV, FLAC, OGG, MP3, AAC, M4A) require a separate extra:

```bash
pip install "pirn[audio]"   # soundfile, numpy, pydub; pydub unavailable on Python 3.13+
```

Use `pirn[signal,audio]` to get both.

---

## Source map

```
pirn_signal/
├── __init__.py                  — lazy package; no module-level scipy/pywavelets imports
├── types/
│   ├── signal_frame.py          — SignalFrame (primary unit of data)
│   ├── spectrum_frame.py        — SpectrumFrame (FFT / PSD output)
│   ├── wavelet_frame.py         — WaveletFrame (DWT coefficient output)
│   └── source_frame.py          — SourceFrame (ICA / NMF decomposition output)
├── filters/                     — IIR/FIR deterministic filter knots (scipy.signal)
├── spectral/                    — FFT, STFT, PSD, Hilbert, cepstrum, chirplet, bispectrum
├── wavelets/                    — DWT, DWPT, CWT, EMD, EEMD, VMD
├── resampling/                  — up/downsample, interpolate, polyphase, streaming buffer
├── adaptive/                    — LMS, NLMS, RLS, APA, subband, Kalman
├── separation/                  — ICA, PCA, NMF, SSA, sparse coding, dictionary learning
├── statistical/                 — MUSIC, ESPRIT, Prony, EKF, UKF, particle filter
├── nonlinear/                   — entropy, Lyapunov, Hurst, correlation dimension, recurrence
├── audio/                       — librosa-backed MIR knots (MFCC, pitch, beat, onset)
├── assemblers/
│   ├── __init__.py
│   └── signal_object_store_assembler.py  — bytes + metadata → SignalPayload
└── disassemblers/
    ├── __init__.py
    ├── signal_object_store_disassembler.py  — SignalPayload → WAV bytes
    ├── spectrum_object_store_disassembler.py — SpectrumPayload → npz bytes
    └── wavelet_object_store_disassembler.py  — WaveletPayload → npz bytes
```

---

## Assembler and Disassembler knots

Raw audio bytes from an object store cross the domain boundary through two knots:

### SignalObjectStoreAssembler

Converts `bytes` (any supported audio format) into a `SignalPayload`. Accepts `body: bytes`, `signal_id: str`, optional `sample_rate_hz: float | None` and `channel_count: int | None` overrides.

```python
from pirn_signal.assemblers.signal_object_store_assembler import SignalObjectStoreAssembler

with Tapestry() as t:
    raw = ObjectStoreReadSource(bucket="audio", key="track.wav", _config=KnotConfig(id="raw"))
    payload = SignalObjectStoreAssembler(body=raw, signal_id="track-001", _config=KnotConfig(id="signal"))
```

Lives in `pirn_signal/assemblers/signal_object_store_assembler.py`. Extends `Assembler`.

### Disassemblers

Three disassemblers convert domain output frames back to bytes for an object store sink:

| Knot | Input | Output | File |
|------|-------|--------|------|
| `SignalObjectStoreDisassembler` | `SignalPayload` | WAV bytes | `disassemblers/signal_object_store_disassembler.py` |
| `SpectrumObjectStoreDisassembler` | `SpectrumPayload` | npz bytes | `disassemblers/spectrum_object_store_disassembler.py` |
| `WaveletObjectStoreDisassembler` | `WaveletPayload` | npz bytes | `disassemblers/wavelet_object_store_disassembler.py` |

All extend `Disassembler`. None perform I/O — they receive materialised payloads and emit bytes for a downstream connector sink.

---

## SignalFrame

`SignalFrame` is a frozen dataclass that extends `PirnOpaqueValue`. It is the contract between every knot in this domain.

```python
@dataclass(frozen=True)
class SignalFrame(PirnOpaqueValue):
    signal_id: str          # stable identifier; propagated and annotated by filter knots
    channel_count: int      # number of interleaved channels
    sample_rate_hz: float   # samples per second
    samples_per_channel: int
    fetched_at: datetime    # UTC timestamp set at ingest; do not override downstream
```

Key points:
- **Immutable.** Knots that transform a signal return a *new* `SignalFrame` with an annotated `signal_id` (e.g. `"ecg:butter-lowpass"`).
- **No sample data.** The frame is a lineage record. Actual numpy arrays are loaded by the scipy/librosa backend during `process()`.
- **Multi-channel.** `channel_count > 1` is valid. Knots that are single-channel-only (e.g. `EmdDecomposer`) must receive `channel_count == 1`; pass a channel-splitter or select channel 0 before wiring.

Constructing a frame at pipeline entry (after decoding an audio record):

```python
from datetime import datetime, timezone
from pirn_signal.types.signal_frame import SignalFrame

frame = SignalFrame(
    signal_id="session-42",
    channel_count=1,
    sample_rate_hz=1000.0,
    samples_per_channel=10_000,
    fetched_at=datetime.now(tz=timezone.utc),
)
```

---

## Canonical pattern

Filter a 1 kHz signal with a Butterworth low-pass, then estimate its power spectral density.

```python
from pirn import Parameter, KnotConfig
from pirn_signal.filters.butterworth_filter import ButterworthFilter
from pirn_signal.spectral.welch_estimator import WelchEstimator

# Entry point — a raw SignalFrame supplied at run time
raw = Parameter("raw_signal", _config=KnotConfig(id="raw_signal"))

filtered = ButterworthFilter(
    signal=raw,
    _config=KnotConfig(id="filtered"),
    order=4,
    cutoff_hz=50.0,
    band_type="lowpass",   # "lowpass" | "highpass" | "bandpass" | "bandstop"
)

psd = WelchEstimator(
    signal=filtered,
    _config=KnotConfig(id="psd"),
    segment_length=256,
    overlap=128,           # must be < segment_length
)
# psd is a Knot[SpectrumFrame]; wire into downstream knots or materialise via Tapestry
```

Extending to wavelets:

```python
from pirn_signal.wavelets.dwt_decomposer import DWTDecomposer

dwt = DWTDecomposer(
    signal=filtered,
    _config=KnotConfig(id="dwt"),
    wavelet_name="db4",
    level_count=5,
)
# dwt emits WaveletFrame
```

---

## Sub-area guide

| Sub-area | When to use | Representative knots |
|---|---|---|
| `filters` | Remove noise, isolate a frequency band, smooth before analysis | `ButterworthFilter`, `NotchFilter`, `FirFilter`, `SavitzkyGolayFilter`, `KalmanSmoother` |
| `spectral` | Frequency-domain analysis, PSD estimation, time-frequency maps | `FftAnalyzer`, `WelchEstimator`, `StftDecomposer`, `HilbertTransformer`, `MultitaperEstimator` |
| `wavelets` | Time-frequency localisation, multi-resolution, non-stationary signals | `DWTDecomposer`, `CwtDecomposer`, `MultiresolutionAnalyzer`, `EmdDecomposer`, `VmdDecomposer` |
| `resampling` | Normalise sample rate before feeding heterogeneous sources into a shared pipeline | `PolyphaseResampler`, `RationalResamplerPipeline`, `Downsampler`, `StreamingBufferManager` |
| `adaptive` | Online noise cancellation, system identification, tracking time-varying signals | `LmsAdaptiveFilter`, `NlmsAdaptiveFilter`, `RlsAdaptiveFilter`, `KalmanFilter` |
| `separation` | Blind source separation, dimensionality reduction, mixed-channel demixing | `IcaDecomposer`, `NmfDecomposer`, `PcaDecomposer`, `SsaDecomposer` |
| `statistical` | Super-resolution frequency estimation, nonlinear state tracking | `MusicEstimator`, `EspritEstimator`, `ExtendedKalmanFilter`, `ParticleFilter` |
| `nonlinear` | Complexity analysis, chaos detection, long-range dependency | `EntropyEstimator`, `LyapunovExponentEstimator`, `HurstExponentEstimator` |
| `audio` | Music / speech feature extraction after ingest and resampling | `MfccExtractor`, `MelSpectrogramExtractor`, `PitchEstimator`, `BeatTracker` |

---

## Anti-patterns

### Passing raw numpy arrays instead of SignalFrame

Every knot's `process()` signature accepts a `SignalFrame`, not a numpy array. Passing raw arrays bypasses the audit trail and breaks lineage.

```python
# WRONG
ButterworthFilter(signal=np.array([...]), ...)

# RIGHT — wrap in a SignalFrame and supply via Parameter
raw = Parameter("raw", _config=KnotConfig(id="raw"))
# ... resolve the Tapestry with SignalFrame(...) bound to "raw"
```

### Using `sample_rate_hz` from KnotConfig instead of the SignalFrame

The sample rate is part of the `SignalFrame` that flows through the pipeline. Hardcoding it in knot parameters and letting it diverge from the frame's `sample_rate_hz` causes silent frequency miscalculations.

### Skipping resampling when mixing sources

If two `SignalFrame` inputs have different `sample_rate_hz` values, run both through `PolyphaseResampler` to a common rate before wiring them into a multi-input knot such as `CrossSpectrumEstimator`.

### Branching before resampling

Placing a filter upstream of a resampler means the filter was designed for the wrong Nyquist frequency. Always resample first.

### Feeding multi-channel frames to single-channel decomposers

`EmdDecomposer`, `VmdDecomposer`, and `EemdDecomposer` operate on single-channel signals. Check `channel_count == 1` before wiring; split channels upstream if needed.

---

## Constraints and gotchas

- **scipy / pywavelets are runtime-only.** The package imports cleanly without them; the `ExtrasLoader` raises at `process()` call time. Guard optional sub-pipelines with `try/except ImportError` in application bootstrap if the extra may be absent.
- **pydub unavailable on Python 3.13+.** `Mp3Format`, `AacFormat`, and `M4aFormat` connectors will raise `ImportError` on Python 3.13+. Use `WavFormat` or `FlacFormat` instead.
- **WelchEstimator: `overlap` must be strictly less than `segment_length`.** Validated at construction; a `ValueError` is raised immediately rather than at run time.
- **ButterworthFilter `band_type` spelling.** The parameter is `band_type`, not `btype`. Accepted values: `"lowpass"`, `"highpass"`, `"bandpass"`, `"bandstop"`.
- **DWTDecomposer parameter is `wavelet_name`, not `wavelet`.** Note: the correct constructor argument is `wavelet_name=`, not `wavelet=`.
- **`SignalFrame` is immutable.** Each knot returns a new frame. Do not attempt to mutate `signal_id` or metadata in-place.
- **`fetched_at` is set at construction.** Do not override it in intermediate knots; it records the original ingest time.

---

## Quick reference

| Task | Knot |
|---|---|
| Low-pass / high-pass / band-pass / notch | `ButterworthFilter`, `LowPassFilter`, `NotchFilter` |
| Polynomial smoothing | `SavitzkyGolayFilter` |
| FIR with custom window | `FirFilter` |
| FFT magnitude/phase spectrum | `FftAnalyzer` |
| PSD via Welch's method | `WelchEstimator` |
| Spectrogram (STFT) | `StftDecomposer` |
| Instantaneous amplitude / phase | `HilbertTransformer` |
| Multi-resolution wavelet decomposition | `DWTDecomposer`, `MultiresolutionAnalyzer` |
| Continuous wavelet transform | `CwtDecomposer` |
| Empirical mode decomposition | `EmdDecomposer` |
| Integer downsampling | `Downsampler` |
| Arbitrary-ratio resampling | `PolyphaseResampler` |
| Streaming overlap-save buffer | `StreamingBufferManager` |
| Online noise cancellation | `LmsAdaptiveFilter`, `NlmsAdaptiveFilter` |
| Blind source separation | `IcaDecomposer` |
| NMF decomposition | `NmfDecomposer` |
| Super-resolution freq estimation | `MusicEstimator`, `EspritEstimator` |
| Nonlinear complexity / entropy | `EntropyEstimator`, `LyapunovExponentEstimator` |
| MFCC / Mel spectrogram | `MfccExtractor`, `MelSpectrogramExtractor` |
| Pitch / beat tracking | `PitchEstimator`, `BeatTracker` |
| Load audio from file (WAV) | `pirn.connectors.file_formats.wav_format.WavFormat` |
| Load audio from file (FLAC/OGG) | `pirn.connectors.file_formats.flac_format.FlacFormat` |

---

*See also: [pirn AGENTIC_USE.md](../../../AGENTIC_USE.md)*
