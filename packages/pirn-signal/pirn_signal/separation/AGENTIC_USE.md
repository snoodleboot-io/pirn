Blind source separation and matrix decomposition — recover latent components from mixed multi-channel signals without knowing the mixing process.

## Mental model

Knots here accept a multi-channel signal matrix (channels × samples) and decompose it into latent components. `ICADecomposer` and `ICARobustDecomposer` maximize statistical independence (cocktail-party problem, EEG artifact removal). `NMFDecomposer` enforces non-negativity (useful for spectrograms). `PCADecomposer` finds orthogonal variance directions. `SparseDecomposer` and `DictionaryLearner` represent signals as sparse combinations of learned atoms. For wavelet-based decomposition, use `pirn_signal.wavelets`.

## Source map

```
├── dictionary_learner.py      DictionaryLearner      — learns a sparse dictionary from training data
├── ica_decomposer.py          ICADecomposer          — FastICA independent component analysis
├── ica_robust_decomposer.py   ICARobustDecomposer    — ICA with robust whitening for noisy/short data
├── nmf_decomposer.py          NMFDecomposer          — non-negative matrix factorization
├── pca_decomposer.py          PCADecomposer          — principal component analysis (whitening + projection)
├── sparse_decomposer.py       SparseDecomposer       — matching pursuit / LASSO sparse representation
├── ssa_decomposer.py          SSADecomposer          — singular spectrum analysis (trajectory matrix SVD)
└── (DictionaryLearner feeds SparseDecomposer for dictionary-based coding)
```

## Canonical pattern

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_signal.separation.ica_decomposer import ICADecomposer

tapestry = Tapestry()

# multichannel_eeg: shape (n_channels, n_samples)
ica = ICADecomposer(
    signal=Parameter("eeg"),
    n_components=20,
    max_iter=500,
    _config=KnotConfig(id="ica"),
)

result = tapestry.run(RunRequest(inputs={"eeg": multichannel_eeg}))
components = result["ica"]   # shape: (n_components, n_samples)
mixing_matrix = ica.mixing_matrix  # (n_channels, n_components)
```

## Anti-patterns

- **Running ICA on fewer samples than channels squared.** ICA requires the data matrix to be overdetermined; violating this causes degenerate solutions. As a rule of thumb, samples > 20 × channels².
- **Using `NMFDecomposer` on signed signals.** NMF requires non-negative input; apply to magnitude spectrograms or rectified signals, not raw waveforms.
- **Treating PCA components as source signals.** PCA maximizes variance, not independence; components are often still mixed. Use ICA if source independence is needed.

## Constraints and gotchas

- ICA component order and sign are arbitrary — post-hoc labeling (e.g. by correlation with a reference) is always required.
- `SSADecomposer` returns singular vectors of the trajectory matrix; the number of meaningful components must be selected by examining singular value drop-off.
- `DictionaryLearner` is a training-phase knot; wire `SparseDecomposer` with `dictionary=DictionaryLearner.output` to encode new signals using the learned atoms.
- `ICARobustDecomposer` uses a pre-whitening step tolerant of rank-deficient data (fewer independent sources than channels); prefer it when channel count is high relative to data length.
- All decomposers are stateful after fitting; refitting on new data requires a new knot instance.
- Install with `pirn-signal[signal]`.

## Quick reference

| Goal | Knot |
|---|---|
| Artifact removal (EEG/EMG) | `ICADecomposer` |
| Noisy / short data ICA | `ICARobustDecomposer` |
| Spectrogram factorization | `NMFDecomposer` |
| Dimensionality reduction | `PCADecomposer` |
| Sparse coding | `SparseDecomposer` |
| Learn sparse dictionary | `DictionaryLearner` |
| Trend/oscillation extraction | `SSADecomposer` |

---

*See also: [signal AGENTIC_USE.md](../AGENTIC_USE.md)*
