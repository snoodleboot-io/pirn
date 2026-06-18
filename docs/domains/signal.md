# Signal Domain

pirn's signal domain (`pirn_signal`) provides digital signal processing (DSP) primitives as first-class pipeline knots. It covers three overlapping areas: **audio** (music and speech), **biosignal** (EEG, ECG, and other physiological recordings handled in conjunction with the health domain), and **general DSP** (filters, spectral analysis, wavelets, adaptive filters, source separation, and nonlinear dynamics). All knots are async, typed, and composable with any other pirn pipeline component.

---

## Install & registration

`pirn_signal` is a standalone distribution. Install the package plus the DSP backends you need:

```bash
pip install pirn-signal                     # pure-Python orchestration layer
pip install 'pirn-signal[signal]'           # scipy + pywavelets + librosa (all DSP knots)
pip install 'pirn-signal[emd]'              # EMD-signal + scipy (empirical mode decomposition)
```

Available extras: `signal`, `emd`. (Audio **file-format** decoding — WAV/FLAC/OGG/MP3/AAC/M4A — is a core connector extra, `pirn[audio]`, not a signal-package extra; see [Audio File Formats](#audio-file-formats) below.)

**Registration (ADR-4):** `import pirn_signal` self-registers the signal-domain knots under `library="pirn"`, so a YAML pipeline can resolve them by bare name. In Python you import the knot classes directly (same effect). To register every installed domain at once, call `pirn.discover_installed_domains()`.

!!! warning "Legacy `pirn.domains.signal` is deprecated"
    The old `pirn.domains.signal` import path still works for one deprecation cycle via a compat shim (it emits a `DeprecationWarning` and defers to `pirn_signal`). Migrate to `pirn_signal` — see the [migration guide](../guides/migrating-to-split-packages.md).

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
| `LowPassFilter` | Butterworth/Chebyshev/elliptic low-pass IIR filter |
| `HighPassFilter` | High-pass IIR filter |
| `BandPassFilter` | Band-pass IIR filter |
| `BandStopFilter` | Band-stop (notch) IIR filter |
| `NotchFilter` | Targeted notch filter (power-line interference removal) |
| `ButterworthFilter` | Butterworth IIR at configurable order and cutoff |
| `ChebyshevType1Filter` | Chebyshev Type I IIR with ripple in the passband |
| `ChebyshevType2Filter` | Chebyshev Type II IIR with ripple in the stopband |
| `EllipticFilter` | Elliptic (Cauer) IIR — minimum order for given spec |
| `BesselFilter` | Bessel IIR with maximally flat group delay |
| `FirFilter` | FIR filter with configurable window and tap count |
| `IirFilter` | Generic IIR filter with user-supplied `b`/`a` coefficients |
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
| `FftAnalyzer` | Fast Fourier Transform magnitude/phase spectrum |
| `StftDecomposer` | Short-Time Fourier Transform (spectrogram) |
| `WelchEstimator` | Welch periodogram PSD estimate |
| `PeriodogramEstimator` | Raw periodogram PSD estimate |
| `MultitaperEstimator` | Multi-taper (Slepian) PSD estimate |
| `CrossSpectrumEstimator` | Cross-spectrum and coherence between two signals |
| `HilbertTransformer` | Analytic signal via Hilbert transform (instantaneous amplitude/phase) |
| `CepstrumAnalyzer` | Real and complex cepstrum analysis |
| `SpectrogramRenderer` | Mel or linear spectrogram image renderer |
| `ChirpletDecomposer` | Chirplet transform decomposition |
| `BispectumAnalyzer` | Bispectrum and bicoherence estimation |

---

### `pirn_signal.wavelets`

Wavelet transform knots backed by `pywavelets` (`PyWavelets`).

| Knot | Description |
|---|---|
| `DwtDecomposer` | Discrete Wavelet Transform (single-level or multi-level) |
| `DwptDecomposer` | Discrete Wavelet Packet Transform |
| `CwtDecomposer` | Continuous Wavelet Transform (Morlet, Mexican hat, etc.) |
| `MultiresolutionAnalyzer` | Mallat multiresolution analysis; decomposes signal into approximation + detail coefficients |
| `WaveletPacketDecomposer` | Full wavelet packet tree decomposition |
| `EmdDecomposer` | Empirical Mode Decomposition (Hilbert-Huang) |
| `EemdDecomposer` | Ensemble EMD for noise-assisted decomposition |
| `VmdDecomposer` | Variational Mode Decomposition |

---

### `pirn_signal.resampling`

Sample rate conversion knots.

| Knot | Description |
|---|---|
| `Upsampler` | Integer upsampling with anti-imaging filter |
| `Downsampler` | Integer downsampling with anti-aliasing filter |
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
| `LmsAdaptiveFilter` | Least Mean Squares (LMS) adaptive filter |
| `NlmsAdaptiveFilter` | Normalised LMS adaptive filter |
| `RlsAdaptiveFilter` | Recursive Least Squares (RLS) adaptive filter |
| `AffinProjectionFilter` | Affine Projection Algorithm (APA) |
| `SubbandAdaptiveFilter` | Subband decomposition + per-band LMS/NLMS |
| `KalmanFilter` | Scalar Kalman filter (linear, time-invariant) |

---

### `pirn_signal.separation`

Source separation and blind decomposition knots.

| Knot | Description |
|---|---|
| `IcaDecomposer` | Fast-ICA blind source separation |
| `IcaRobustDecomposer` | Robust ICA with outlier handling |
| `PcaDecomposer` | Principal Component Analysis projection |
| `NmfDecomposer` | Non-negative Matrix Factorisation |
| `SsaDecomposer` | Singular Spectrum Analysis |
| `SparseDecomposer` | Sparse coding (OMP / LASSO) |
| `DictionaryLearner` | Online dictionary learning for sparse representations |

---

### `pirn_signal.statistical`

Statistical signal processing and spectral estimation knots.

| Knot | Description |
|---|---|
| `MusicEstimator` | MUSIC super-resolution frequency estimator |
| `EspritEstimator` | ESPRIT frequency estimator |
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
| `MfccExtractor` | Mel-frequency cepstral coefficients |
| `PitchEstimator` | Fundamental frequency / pitch estimation |
| `OnsetDetector` | Note onset detection |
| `BeatTracker` | Beat and tempo tracking |
| `MusicInformationRetriever` | High-level MIR features (tempo, key, chroma, etc.) |

---

## Usage Patterns

### Filtering then spectral analysis

```python
from pirn import knot, Parameter, Tapestry, KnotConfig, RunRequest
from pirn_signal.filters.butterworth_filter import ButterworthFilter
from pirn_signal.spectral.welch_estimator import WelchEstimator

raw_signal = Parameter("signal", bytes, _config=KnotConfig(id="signal"))

filtered = ButterworthFilter(
    signal=raw_signal,
    _config=KnotConfig(id="filtered"),
    order=4,
    cutoff_hz=50.0,
    fs=1000.0,
    btype="low",
)

psd = WelchEstimator(
    signal=filtered,
    _config=KnotConfig(id="psd"),
    fs=1000.0,
    nperseg=256,
)
```

### Decoding an audio file and extracting MFCCs

```python
from pirn.connectors.file_formats.wav_format import WavFormat
from pirn_signal.audio.mfcc_extractor import MfccExtractor

# Outside the pipeline — load bytes from disk/storage
wav_bytes = Path("recording.wav").read_bytes()
format_ = WavFormat()

# Decode to pirn records
records = await format_.decode(wav_bytes)
# records[0] has sample_rate, n_channels, sampwidth, n_frames, frames

# In a pipeline, wire the decoded record to MfccExtractor
```

### Wavelet decomposition

```python
from pirn_signal.wavelets.dwt_decomposer import DwtDecomposer

decomposed = DwtDecomposer(
    signal=filtered,
    _config=KnotConfig(id="dwt"),
    wavelet="db4",
    level=5,
)
```

---

## Types

The `pirn_signal.types` package exposes shared typed containers used across sub-packages:

| Type | Fields | Description |
|---|---|---|
| `SignalFrame` | `data: bytes`, `sample_rate: float`, `n_channels: int`, `n_samples: int` | Single-channel or multi-channel signal window |
| `SpectrumFrame` | `frequencies: bytes`, `amplitudes: bytes`, `sample_rate: float` | FFT/PSD result |
| `WaveletFrame` | `coefficients: bytes`, `wavelet: str`, `level: int` | DWT coefficient output |
| `SourceFrame` | `components: bytes`, `n_components: int`, `mixing_matrix: bytes` | ICA/NMF decomposition output |

---

## Install Extras

```bash
pip install "pirn-signal[signal]"
```

| Extra | Libraries installed | What it enables |
|---|---|---|
| `signal` | `scipy>=1.12`, `pywavelets>=1.5`, `librosa>=0.10` | All signal domain knots (filters, spectral, wavelets, resampling, adaptive, separation, nonlinear, audio analysis) |
| `audio` (separate) | `soundfile`, `numpy`, `pydub` | WAV/FLAC/OGG/MP3/AAC/M4A format connectors |

`scipy` and `pywavelets` are the core dependencies. `librosa` adds the audio analysis knots in `pirn_signal.audio` and pulls in `numpy` and `soundfile` as transitive dependencies.

---

## Connector boundaries

Domain payloads enter and leave the signal domain through assembler/disassembler knots. The ingestor pattern is abolished.

`SignalObjectStoreAssembler` replaces `AudioFileIngestor` — it receives raw bytes from an `ObjectStoreReadSource` connector and produces a `SignalPayload`. No I/O occurs inside the assembler.

Three disassemblers cover the signal domain's output payload types:

| Disassembler | Input | Output |
|---|---|---|
| `SignalObjectStoreDisassembler` | `SignalPayload` | `bytes` |
| `SpectrumObjectStoreDisassembler` | `SpectrumFrame` | `bytes` |
| `WaveletObjectStoreDisassembler` | `WaveletFrame` | `bytes` |

All assemblers and disassemblers live under `pirn_signal/assemblers/` and `pirn_signal/disassemblers/` respectively.

**See also:** [Health Domain — Biosignal Formats](health.md#healthcare-biosignal-formats), [File Formats — Connectors](../connectors/index.md)
