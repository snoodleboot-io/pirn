Spectral analysis and frequency-domain transforms — estimate power spectra, compute FFTs, and decompose signals into time-frequency representations.

## Mental model

Knots here consume a time-domain `signal` (and `fs`) and produce frequency-domain representations: power spectral densities, complex spectra, or time-frequency maps. They do not modify the signal — they describe it. Non-parametric estimators (Welch, Bartlett, Periodogram) average periodograms; parametric spectral estimation lives in `pirn_signal.statistical`. For reconstruction from a spectrum, use `IFftReconstructor` or `IstftReconstructor`.

## Source map

```
├── bartlett_psd_estimator.py    BartlettPsdEstimator     — PSD via averaged non-overlapping segments
├── bispectrum_analyzer.py       BispectumAnalyzer        — third-order spectral analysis for nonlinear coupling
├── cepstrum_analyzer.py         CepstrumAnalyzer         — lifters speech/echo structure via inverse log-spectrum
├── chirplet_decomposer.py       ChirpletDecomposer       — time-frequency decomposition with chirping atoms
├── cross_spectrum_estimator.py  CrossSpectrumEstimator   — cross-power spectral density between two channels
├── fft_analyzer.py              FftAnalyzer              — single-sided FFT magnitude/phase spectrum
├── hilbert_transformer.py       HilbertTransformer       — analytic signal via Hilbert transform (envelope, IF)
├── ifft_reconstructor.py        IFftReconstructor        — inverse FFT back to time domain
├── istft_reconstructor.py       IstftReconstructor       — overlap-add reconstruction from STFT frames
├── multitaper_estimator.py      MultitaperEstimator      — low-variance PSD via Slepian tapers (Thomson)
├── periodogram_estimator.py     PeriodogramEstimator     — raw squared-magnitude FFT PSD
├── spectrogram_renderer.py      SpectrogramRenderer      — magnitude spectrogram as 2-D array (time × freq)
├── stft_decomposer.py           StftDecomposer           — short-time Fourier transform frames
├── welch_estimator.py           WelchEstimator           — PSD via averaged overlapping segments (Welch)
└── wavelet_coherence_estimator.py WaveletCoherenceEstimator — time-frequency coherence via CWT (if present)
```

## Canonical pattern

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn_signal.spectral.welch_estimator import WelchEstimator
from pirn_signal.spectral.stft_decomposer import StftDecomposer

tapestry = Tapestry()

psd = WelchEstimator(
    signal=Parameter("eeg"),
    fs=256,
    nperseg=512,
    noverlap=256,
    window="hann",
    _config=KnotConfig(id="psd"),
)
stft = StftDecomposer(
    signal=Parameter("eeg"),
    fs=256,
    nperseg=256,
    noverlap=128,
    _config=KnotConfig(id="stft"),
)

result = tapestry.run(RunRequest(inputs={"eeg": my_eeg}))
freqs, power = result["psd"]   # (freq_bins,), (freq_bins,)
t, f, Zxx   = result["stft"]   # time, freq, complex array
```

## Anti-patterns

- **Filtering with spectral knots.** Zeroing FFT bins is not a proper filter — use `filters/` knots which apply proper filter design.
- **Using `PeriodogramEstimator` for noisy signals.** The raw periodogram is inconsistent (variance does not decrease with N); prefer `WelchEstimator` or `MultitaperEstimator`.
- **Ignoring window choice.** The default rectangular window causes severe spectral leakage; always specify a window (e.g. `"hann"`) unless you have a specific reason.

## Constraints and gotchas

- `FftAnalyzer` output frequencies span `[0, fs/2]` (one-sided); negative-frequency content is discarded.
- `CrossSpectrumEstimator` requires two aligned signals of the same length and `fs`.
- `IstftReconstructor` must receive the same `nperseg` and `noverlap` used by `StftDecomposer` or reconstruction will be wrong.
- `BispectumAnalyzer` is computationally O(N²) in frequency bins; limit `nfft` for long signals.
- `HilbertTransformer` assumes the input is analytic-signal-ready (narrowband or pre-filtered); apply a bandpass filter first for broadband signals.
- Install with `pirn-signal[signal]`.

## Quick reference

| Goal | Knot |
|---|---|
| Dominant frequency / spectrum | `FftAnalyzer` |
| Low-variance PSD | `WelchEstimator` or `MultitaperEstimator` |
| Time-varying spectrum | `StftDecomposer` + `SpectrogramRenderer` |
| Envelope / instantaneous frequency | `HilbertTransformer` |
| Channel coherence | `CrossSpectrumEstimator` |
| Echo / formant structure | `CepstrumAnalyzer` |
| Nonlinear coupling detection | `BispectumAnalyzer` |
| Reconstruct from STFT | `IstftReconstructor` |

---

*See also: [signal AGENTIC_USE.md](../AGENTIC_USE.md)*
