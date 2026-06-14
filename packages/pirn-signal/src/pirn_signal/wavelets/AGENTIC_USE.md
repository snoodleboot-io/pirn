Wavelet and empirical mode decomposition — multi-resolution analysis, time-frequency localization, and adaptive signal decomposition.

## Mental model

Knots here decompose a signal into components that are simultaneously localized in time and frequency. `DwtDecomposer` (discrete wavelet) and `DwptDecomposer` (wavelet packet) produce a tree of sub-bands at dyadic scales; `CwtDecomposer` produces a continuous scalogram. `EmdDecomposer` and `EemdDecomposer` adaptively extract intrinsic mode functions (IMFs) without a fixed basis. `IdwtReconstructor` inverts a DWT decomposition back to the time domain. Spectral analysis (power spectra, FFT) belongs in `pirn_signal.spectral`.

## Source map

```
├── cwt_decomposer.py              CwtDecomposer             — continuous wavelet transform (scalogram)
├── dwpt_decomposer.py             DwptDecomposer            — discrete wavelet packet transform (full tree)
├── dwt_decomposer.py              DwtDecomposer             — discrete wavelet transform (approximation + details)
├── eemd_decomposer.py             EemdDecomposer            — ensemble EMD for noise-assisted decomposition
├── emd_decomposer.py              EmdDecomposer             — empirical mode decomposition into IMFs
├── idwt_reconstructor.py          IdwtReconstructor         — inverse DWT, reconstructs signal from coefficients
├── multiresolution_analyzer.py    MultiresolutionAnalyzer   — energy and statistics per DWT level
├── swt_decomposer.py              SwtDecomposer             — stationary (undecimated) wavelet transform
├── vmd_decomposer.py              VmdDecomposer             — variational mode decomposition
├── wavelet_denoiser.py            WaveletDenoiser           — thresholds DWT coefficients for denoising
├── wavelet_packet_decomposer.py   WaveletPacketDecomposer   — alias for DwptDecomposer with richer node API
└── (IdwtReconstructor pairs with DwtDecomposer/SwtDecomposer)
```

## Canonical pattern

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn_signal.wavelets.dwt_decomposer import DwtDecomposer
from pirn_signal.wavelets.wavelet_denoiser import WaveletDenoiser

tapestry = Tapestry()

dwt = DwtDecomposer(
    signal=Parameter("noisy"),
    wavelet="db4",
    level=5,
    _config=KnotConfig(id="dwt"),
)
denoised = WaveletDenoiser(
    coefficients=dwt.output,
    threshold_mode="soft",
    _config=KnotConfig(id="denoised"),
)

result = tapestry.run(RunRequest(inputs={"noisy": my_signal}))
clean = result["denoised"]
```

## Anti-patterns

- **Using `CwtDecomposer` for denoising.** CWT is redundant (non-orthogonal) and not designed for reconstruction; use `DwtDecomposer` + `WaveletDenoiser` + `IdwtReconstructor` instead.
- **Choosing `EmdDecomposer` for deterministic pipelines.** EMD is sensitive to noise and end effects; `EemdDecomposer` (with ensemble averaging) is more stable, and both are non-deterministic by nature.
- **Expecting `DwptDecomposer` output to be the same length as the input.** Each level halves the length; account for this when wiring downstream knots.

## Constraints and gotchas

- `DwtDecomposer` requires signal length to be a power of 2 (or will pad automatically — check `pad_mode` parameter).
- `SwtDecomposer` output length equals input length at every level (no downsampling), but memory use scales with `level`.
- `VmdDecomposer` requires specifying the number of modes `K` upfront; there is no automatic mode selection.
- `IdwtReconstructor` must receive coefficients from the same `wavelet` family and `level` used in `DwtDecomposer` or results will be garbage.
- `EemdDecomposer` is computationally expensive (runs EMD N times); reduce `n_ensembles` for prototyping.
- Install with `pirn-signal[signal]`.

## Quick reference

| Goal | Knot |
|---|---|
| Multi-resolution decomposition | `DwtDecomposer` |
| Time-frequency scalogram | `CwtDecomposer` |
| Wavelet-domain denoising | `WaveletDenoiser` |
| Reconstruct from DWT | `IdwtReconstructor` |
| Adaptive IMF extraction | `EmdDecomposer` / `EemdDecomposer` |
| Noise-robust adaptive decomp | `EemdDecomposer` or `VmdDecomposer` |
| Energy per sub-band | `MultiresolutionAnalyzer` |
| Full wavelet packet tree | `DwptDecomposer` |

---

*See also: [signal AGENTIC_USE.md](../AGENTIC_USE.md)*
