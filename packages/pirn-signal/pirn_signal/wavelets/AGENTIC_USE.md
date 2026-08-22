Wavelet and empirical mode decomposition — multi-resolution analysis, time-frequency localization, and adaptive signal decomposition.

## Mental model

Knots here decompose a signal into components that are simultaneously localized in time and frequency. `DWTDecomposer` (discrete wavelet) and `DWPTDecomposer` (wavelet packet) produce a tree of sub-bands at dyadic scales; `CWTDecomposer` produces a continuous scalogram. `EMDDecomposer` and `EEMDDecomposer` adaptively extract intrinsic mode functions (IMFs) without a fixed basis. `IDWTReconstructor` inverts a DWT decomposition back to the time domain. Spectral analysis (power spectra, FFT) belongs in `pirn_signal.spectral`.

## Source map

```
├── cwt_decomposer.py              CWTDecomposer             — continuous wavelet transform (scalogram)
├── dwpt_decomposer.py             DWPTDecomposer            — discrete wavelet packet transform (full tree)
├── dwt_decomposer.py              DWTDecomposer             — discrete wavelet transform (approximation + details)
├── eemd_decomposer.py             EEMDDecomposer            — ensemble EMD for noise-assisted decomposition
├── emd_decomposer.py              EMDDecomposer             — empirical mode decomposition into IMFs
├── idwt_reconstructor.py          IDWTReconstructor         — inverse DWT, reconstructs signal from coefficients
├── multiresolution_analyzer.py    MultiresolutionAnalyzer   — energy and statistics per DWT level
├── swt_decomposer.py              SWTDecomposer             — stationary (undecimated) wavelet transform
├── vmd_decomposer.py              VMDDecomposer             — variational mode decomposition
├── wavelet_denoiser.py            WaveletDenoiser           — thresholds DWT coefficients for denoising
├── wavelet_packet_decomposer.py   WaveletPacketDecomposer   — alias for DWPTDecomposer with richer node API
└── (IDWTReconstructor pairs with DWTDecomposer/SWTDecomposer)
```

## Canonical pattern

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_signal.wavelets.dwt_decomposer import DWTDecomposer
from pirn_signal.wavelets.wavelet_denoiser import WaveletDenoiser

tapestry = Tapestry()

dwt = DWTDecomposer(
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

- **Using `CWTDecomposer` for denoising.** CWT is redundant (non-orthogonal) and not designed for reconstruction; use `DWTDecomposer` + `WaveletDenoiser` + `IDWTReconstructor` instead.
- **Choosing `EMDDecomposer` for deterministic pipelines.** EMD is sensitive to noise and end effects; `EEMDDecomposer` (with ensemble averaging) is more stable, and both are non-deterministic by nature.
- **Expecting `DWPTDecomposer` output to be the same length as the input.** Each level halves the length; account for this when wiring downstream knots.

## Constraints and gotchas

- `DWTDecomposer` requires signal length to be a power of 2 (or will pad automatically — check `pad_mode` parameter).
- `SWTDecomposer` output length equals input length at every level (no downsampling), but memory use scales with `level`.
- `VMDDecomposer` requires specifying the number of modes `K` upfront; there is no automatic mode selection.
- `IDWTReconstructor` must receive coefficients from the same `wavelet` family and `level` used in `DWTDecomposer` or results will be garbage.
- `EEMDDecomposer` is computationally expensive (runs EMD N times); reduce `n_ensembles` for prototyping.
- Install with `pirn-signal[signal]`.

## Quick reference

| Goal | Knot |
|---|---|
| Multi-resolution decomposition | `DWTDecomposer` |
| Time-frequency scalogram | `CWTDecomposer` |
| Wavelet-domain denoising | `WaveletDenoiser` |
| Reconstruct from DWT | `IDWTReconstructor` |
| Adaptive IMF extraction | `EMDDecomposer` / `EEMDDecomposer` |
| Noise-robust adaptive decomp | `EEMDDecomposer` or `VMDDecomposer` |
| Energy per sub-band | `MultiresolutionAnalyzer` |
| Full wavelet packet tree | `DWPTDecomposer` |

---

*See also: [signal AGENTIC_USE.md](../AGENTIC_USE.md)*
