# Signal Domain

pirn's signal domain (`pirn_signal`) provides digital signal processing (DSP) primitives as first-class pipeline knots. It covers three overlapping areas: **audio** (music and speech), **biosignal** (EEG, ECG, and other physiological recordings handled in conjunction with the health domain), and **general DSP** (filters, spectral analysis, wavelets, adaptive filters, source separation, and nonlinear dynamics). All knots are async, typed, and composable with any other pirn pipeline component.

---

## Install & registration

`pirn_signal` is a standalone distribution. Install the package plus the DSP backends you need:

```bash
pip install pirn-signal                     # pure-Python orchestration layer
pip install 'pirn-signal[signal]'           # scipy + pywavelets + librosa + vmdpy (most DSP knots)
pip install 'pirn-signal[emd]'              # EMD-signal + scipy (empirical mode decomposition)
pip install 'pirn-signal[separation]'       # scikit-learn (ICA/PCA/NMF/sparse-coding knots + speaker diarization)
```

Available extras: `signal`, `emd`, `separation`. (Audio **file-format** decoding — WAV/FLAC/OGG/MP3/AAC/M4A — is a core connector extra, `pirn[audio]`, not a signal-package extra; see [Audio File Formats](#audio-file-formats) below.)

**Registration (ADR-4):** `import pirn_signal` self-registers the signal-domain knots under `library="pirn"`, so a YAML pipeline can resolve them by bare name. In Python you import the knot classes directly (same effect). To register every installed domain at once, call `DomainDiscovery.discover_installed_domains()` (`pirn.domain_discovery`).

---

## Audio File Formats

Audio formats live on core's connector surface under `pirn.connectors.file_formats.*` and follow the standard `BatchFileFormat` interface: `decode(bytes) -> Iterable[record]` and `encode(Iterable[record]) -> bytes`. All audio formats emit **one record per file**.

### WavFormat

Backed by the Python standard library `wave` module — no optional dependencies required.

**Record shape:**

```python
{
    "sample_rate":  int,
    "n_channels":   int,
    "sampwidth":    int,    # bytes per sample (1 = 8-bit, 2 = 16-bit, 4 = 32-bit)
    "n_frames":     int,
    "frames":       bytes,  # raw interleaved PCM bytes
}
```

**Dependencies:** stdlib only.

---

### FlacFormat

Backed by `soundfile` (libsndfile Python binding). Uses a temporary file internally because `soundfile` requires a seekable path or file handle.

**Record shape:**

```python
{
    "sample_rate":  int,
    "n_channels":   int,
    "n_frames":     int,
    "frames":       bytes,  # raw float32 interleaved PCM bytes
}
```

**Dependencies:** `soundfile`, `numpy`. Install with `pip install pirn[audio]`.

---

### OggFormat

Ogg Vorbis via `soundfile`. Record shape is identical to `FlacFormat` (float32 interleaved PCM). Uses a temporary file internally.

**Dependencies:** `soundfile`, `numpy`. Install with `pip install pirn[audio]`.

---

### Mp3Format

Backed by `pydub`, which wraps ffmpeg. **ffmpeg must be on `PATH` at runtime.**

**Record shape:**

```python
{
    "sample_rate":   int,
    "n_channels":    int,
    "sample_width":  int,   # bytes per sample
    "n_frames":      int,
    "frames":        bytes, # raw PCM bytes
}
```

**Dependencies:** `pydub`, ffmpeg on PATH. Install with `pip install pirn[audio]` and ensure `ffmpeg` is installed.

**Python 3.13+ note:** `pydub` currently does not publish wheels for Python 3.13 or later. On Python 3.13+, `Mp3Format` (and `AacFormat`, `M4aFormat`) will fail to import with an `ImportError`. Use `FlacFormat` or `OggFormat` for lossless workflows, or WAV for uncompressed PCM, until `pydub` ships compatible wheels.

---

### AacFormat

AAC (ADTS stream) via `pydub`/ffmpeg. Record shape is identical to `Mp3Format`.

**Dependencies:** `pydub`, ffmpeg on PATH. Same Python 3.13+ caveat applies.

---

### M4aFormat

M4A (AAC in MP4 container) via `pydub`/ffmpeg. Record shape is identical to `Mp3Format`. On encode, the container is written using pydub's `"ipod"` format specifier (which produces a valid `.m4a`).

**Dependencies:** `pydub`, ffmpeg on PATH. Same Python 3.13+ caveat applies.

---

### Format comparison

| Format | Class | Read | Write | Dependency | Python 3.13+ |
|---|---|---|---|---|---|
| WAV | `WavFormat` | yes | yes | stdlib | yes |
| FLAC | `FlacFormat` | yes | yes | soundfile, numpy | yes |
| Ogg Vorbis | `OggFormat` | yes | yes | soundfile, numpy | yes |
| MP3 | `Mp3Format` | yes | yes | pydub + ffmpeg | no (pydub) |
| AAC | `AacFormat` | yes | yes | pydub + ffmpeg | no (pydub) |
| M4A | `M4aFormat` | yes | yes | pydub + ffmpeg | no (pydub) |

---

## Signal Processing Sub-packages

### `pirn_signal.filters`

Deterministic digital filter knots backed by `scipy.signal`.

| Knot | Description |
|---|---|
| `LowPassFilter` | Butterworth low-pass IIR filter (configurable order, default 4) |
| `HighPassFilter` | Butterworth high-pass IIR filter (configurable order, default 4) |
| `BandPassFilter` | Butterworth band-pass IIR filter (configurable order, default 4) |
| `BandStopFilter` | Butterworth band-stop (notch) IIR filter (configurable order, default 4) |
| `NotchFilter` | Targeted notch filter (power-line interference removal) |
| `ButterworthFilter` | Butterworth IIR at configurable order and cutoff |
| `ChebyshevType1Filter` | Chebyshev Type I IIR with ripple in the passband |
| `ChebyshevType2Filter` | Chebyshev Type II IIR with ripple in the stopband |
| `EllipticFilter` | Elliptic (Cauer) IIR — minimum order for given spec |
| `BesselFilter` | Bessel IIR with maximally flat group delay |
| `FIRFilter` | FIR filter with configurable window and tap count |
| `IIRFilter` | Generic IIR filter with user-supplied `b`/`a` coefficients |
| `MatchedFilter` | Matched filter (cross-correlation with a reference signal) |
| `SavitzkyGolayFilter` | Savitzky-Golay polynomial smoothing filter |
| `WienerFilter` | Wiener filter for noise reduction |
| `KalmanSmoother` | Rauch-Tung-Striebel Kalman smoother |
| `PolyphaseDecimator` | Polyphase anti-aliasing decimator |

---

### `pirn_signal.spectral`

Spectral analysis knots.

| Knot | Description |
|---|---|
| `FFTAnalyzer` | Fast Fourier Transform magnitude/phase spectrum |
| `STFTDecomposer` | Short-Time Fourier Transform (spectrogram) |
| `WelchEstimator` | Welch periodogram PSD estimate |
| `PeriodogramEstimator` | Raw periodogram PSD estimate |
| `MultitaperEstimator` | Multi-taper (Slepian) PSD estimate |
| `CrossSpectrumEstimator` | Cross-spectrum and coherence between two signals |
| `HilbertTransformer` | Analytic signal via Hilbert transform (instantaneous amplitude/phase) |
| `CepstrumAnalyzer` | Real and complex cepstrum analysis |
| `SpectrogramRenderer` | Mel or linear spectrogram image renderer |
| `ChirpletDecomposer` | Chirplet transform decomposition |
| `BispectrumAnalyzer` | Bispectrum and bicoherence estimation |

---

### `pirn_signal.wavelets`

Wavelet transform knots backed by `pywavelets` (`PyWavelets`).

| Knot | Description |
|---|---|
| `DWTDecomposer` | Discrete Wavelet Transform (single-level or multi-level) |
| `DWPTDecomposer` | Discrete Wavelet Packet Transform (full wavelet packet tree) |
| `CWTDecomposer` | Continuous Wavelet Transform (Morlet, Mexican hat, etc.) |
| `MultiresolutionAnalyzer` | Mallat multiresolution analysis; decomposes signal into approximation + detail coefficients |
| `EMDDecomposer` | Empirical Mode Decomposition (Hilbert-Huang) |
| `EEMDDecomposer` | Ensemble EMD for noise-assisted decomposition |
| `VMDDecomposer` | Variational Mode Decomposition |

---

### `pirn_signal.resampling`

Sample rate conversion knots.

| Knot | Description |
|---|---|
| `Upsampler` | Integer zero-stuff upsampling (no reconstruction filter applied) |
| `Downsampler` | Integer decimation by sample dropping (no anti-aliasing filter applied; filter upstream first) |
| `Decimator` | Decimation (downsampling without pre-filtering) |
| `Interpolator` | Arbitrary-ratio interpolation (linear, cubic, sinc) |
| `PolyphaseResampler` | Polyphase filter bank resampler |
| `RationalResamplerPipeline` | Rational (P/Q) resampler using polyphase stages |
| `StreamingBufferManager` | Overlap-save/overlap-add buffer for streaming pipelines |

---

### `pirn_signal.adaptive`

Adaptive filter knots that update coefficients online.

| Knot | Description |
|---|---|
| `LMSAdaptiveFilter` | Least Mean Squares (LMS) adaptive filter |
| `NLMSAdaptiveFilter` | Normalised LMS adaptive filter |
| `RLSAdaptiveFilter` | Recursive Least Squares (RLS) adaptive filter |
| `AffineProjectionFilter` | Affine Projection Algorithm (APA) |
| `SubbandAdaptiveFilter` | Subband decomposition + per-band LMS/NLMS |
| `KalmanFilter` | Scalar Kalman filter (linear, time-invariant) |

---

### `pirn_signal.separation`

Source separation and blind decomposition knots.

| Knot | Description |
|---|---|
| `ICADecomposer` | Fast-ICA blind source separation |
| `ICARobustDecomposer` | Robust ICA with outlier handling |
| `PCADecomposer` | Principal Component Analysis projection |
| `NMFDecomposer` | Non-negative Matrix Factorisation |
| `SSADecomposer` | Singular Spectrum Analysis |
| `SparseDecomposer` | Sparse coding (OMP / LASSO) |
| `DictionaryLearner` | Online dictionary learning for sparse representations |

---

### `pirn_signal.statistical`

Statistical signal processing and spectral estimation knots.

| Knot | Description |
|---|---|
| `MUSICEstimator` | MUSIC super-resolution frequency estimator |
| `ESPRITEstimator` | ESPRIT frequency estimator |
| `PisarenkoEstimator` | Pisarenko harmonic decomposition |
| `PronyEstimator` | Prony method for damped sinusoid estimation |
| `ExtendedKalmanFilter` | Extended Kalman filter for nonlinear state estimation |
| `UnscentedKalmanFilter` | Unscented Kalman filter (sigma-point method) |
| `ParticleFilter` | Sequential Monte Carlo particle filter |

---

### `pirn_signal.nonlinear`

Nonlinear dynamics and complexity analysis knots.

| Knot | Description |
|---|---|
| `EntropyEstimator` | Sample, approximate, and permutation entropy |
| `LyapunovExponentEstimator` | Largest Lyapunov exponent (Wolf method) |
| `HurstExponentEstimator` | Hurst exponent via R/S analysis |
| `CorrelationDimensionEstimator` | Grassberger-Procaccia correlation dimension |
| `RecurrenceAnalyzer` | Recurrence plot and recurrence quantification analysis |

---

### `pirn_signal.audio`

High-level audio analysis knots backed by `librosa`.

> **Note:** `AudioFileIngestor` has been removed. Use `SignalObjectStoreAssembler` to receive raw bytes from an `ObjectStoreReadSource` connector and produce a `SignalPayload`. The ingestor pattern is abolished in this domain. See [Connector boundaries](#connector-boundaries) below.

| Knot | Description |
|---|---|
| `AudioResampler` | Sample rate conversion using `librosa.resample` |
| `MelSpectrogramExtractor` | Mel-scale spectrogram extraction |
| `MFCCExtractor` | Mel-frequency cepstral coefficients |
| `PitchEstimator` | Fundamental frequency / pitch estimation |
| `OnsetDetector` | Note onset detection |
| `BeatTracker` | Beat and tempo tracking |
| `MusicInformationRetriever` | High-level MIR features (tempo, key, chroma, etc.) |

---

## Usage Patterns

### Filtering then spectral analysis

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.filters.butterworth_filter import ButterworthFilter
from pirn_signal.spectral.welch_estimator import WelchEstimator
from pirn_signal.types.signal_payload import SignalPayload

# raw_signal resolves to a SignalPayload at run time (e.g. from
# SignalObjectStoreAssembler); sample_rate_hz travels with it on the frame.
raw_signal = Parameter("signal", SignalPayload, _config=KnotConfig(id="signal"))

filtered = ButterworthFilter(
    signal=raw_signal,
    _config=KnotConfig(id="filtered"),
    order=4,
    cutoff_hz=50.0,
    band_type="lowpass",
)

psd = WelchEstimator(
    signal=filtered,
    _config=KnotConfig(id="psd"),
    segment_length=256,
)
```

### Assembling an audio file and extracting MFCCs

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.assemblers.signal_object_store_assembler import SignalObjectStoreAssembler
from pirn_signal.audio.mfcc_extractor import MFCCExtractor

# `body` resolves to raw bytes at run time — typically from an
# ObjectStoreReadSource connector knot reading e.g. "recording.wav"
body = Parameter("body", bytes, _config=KnotConfig(id="body"))

signal = SignalObjectStoreAssembler(
    body=body,
    signal_id="recording",
    _config=KnotConfig(id="signal"),
)

mfcc = MFCCExtractor(
    signal=signal,
    _config=KnotConfig(id="mfcc"),
    n_mfcc=13,
    n_fft=2048,
    hop_length=512,
)
```

### Wavelet decomposition

```python
from pirn_signal.wavelets.dwt_decomposer import DWTDecomposer

decomposed = DWTDecomposer(
    signal=filtered,
    _config=KnotConfig(id="dwt"),
    wavelet_name="db4",
    level_count=5,
)
```

---

## Types

The `pirn_signal.types` package exposes shared typed containers used across sub-packages.
Each `*Frame` is a small, immutable lineage/metadata record; each corresponding
`*Payload` pairs that frame with the actual array data (`payload.frame` / `payload.data`).

| Frame | Frame fields | Payload `data` | Description |
|---|---|---|---|
| `SignalFrame` | `signal_id: str`, `channel_count: int`, `sample_rate_hz: float`, `samples_per_channel: int`, `fetched_at: datetime` | `np.ndarray`, shaped `(channels, samples)` or `(samples,)` | Time-domain signal |
| `SpectrumFrame` | `signal_id: str`, `frequency_bins: int`, `frequency_resolution_hz: float` | `np.ndarray`, shaped `(channels, bins)` or `(bins,)` | FFT/PSD/spectrogram result |
| `WaveletFrame` | `signal_id: str`, `wavelet_name: str`, `scale_count: int` | `list[np.ndarray]`, one array per decomposition level | Wavelet decomposition |
| `SourceFrame` | `signal_id: str`, `source_count: int`, `mixing_matrix_shape: tuple[int, int]` | `np.ndarray`, shaped `(n_sources, n_samples)` | ICA/PCA/NMF/SSA decomposition |
| `FeatureFrame` | `signal_id: str`, `channel_count: int`, `feature_names: tuple[str, ...]` | `np.ndarray`, shaped `(channels, n_features)` (or wider for frame-indexed features) | Named per-channel feature set |

`SignalPayload.derive(tag, data, **frame_overrides)` builds a new `SignalPayload` from
an existing one, tagging `signal_id` with `:{tag}` and inheriting `channel_count` /
`sample_rate_hz` unless overridden — most filter and transform knots use it instead of
constructing `SignalFrame` by hand.

---

## Install Extras

```bash
pip install "pirn-signal[signal]"
```

| Extra | Libraries installed | What it enables |
|---|---|---|
| `signal` | `scipy>=1.12`, `pywavelets>=1.5`, `librosa>=0.10`, `vmdpy>=0.2` | Filters, spectral, wavelets (including `VMDDecomposer`'s `backend="vmdpy"`), resampling, adaptive, nonlinear, and audio analysis knots |
| `emd` | `EMD-signal>=1.6`, `scipy>=1.12` | `EMDDecomposer`, `EEMDDecomposer` |
| `separation` | `scikit-learn>=1.3` | `pirn_signal.separation` knots (ICA/PCA/NMF/sparse coding/dictionary learning) and `SpeakerDiarizationPipeline`'s clustering step |
| `audio` (separate) | `soundfile`, `numpy`, `pydub` | WAV/FLAC/OGG/MP3/AAC/M4A format connectors |

`scipy` and `pywavelets` are the core DSP dependencies. `librosa` adds the audio analysis knots in `pirn_signal.audio` and pulls in `numpy` and `soundfile` as transitive dependencies. `vmdpy` backs `VMDDecomposer`'s default `backend="vmdpy"`; without it, pass `backend="numpy"` to use the built-in fallback (see [`pirn_signal.wavelets`](#pirn_signalwavelets) below), or install `pirn-signal[signal]`. `scikit-learn` is a separate extra because it is only needed by the source-separation sub-package and one audio knot, not the rest of the DSP surface.

---

## Connector boundaries

Domain payloads enter and leave the signal domain through assembler/disassembler knots. The ingestor pattern is abolished.

`SignalObjectStoreAssembler` replaces `AudioFileIngestor` — it receives raw bytes from an `ObjectStoreReadSource` connector and produces a `SignalPayload`. No I/O occurs inside the assembler.

Three disassemblers cover the signal domain's output payload types:

| Disassembler | Input | Output |
|---|---|---|
| `SignalObjectStoreDisassembler` | `SignalPayload` | `bytes` |
| `SpectrumObjectStoreDisassembler` | `SpectrumPayload` | `bytes` |
| `WaveletObjectStoreDisassembler` | `WaveletPayload` | `bytes` |

All assemblers and disassemblers live under `pirn_signal/assemblers/` and `pirn_signal/disassemblers/` respectively.

**See also:** [Health Domain — Biosignal Formats](health.md#healthcare-biosignal-formats), [File Formats — Connectors](../connectors/index.md)
