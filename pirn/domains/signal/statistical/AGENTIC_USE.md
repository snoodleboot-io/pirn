Statistical signal processing — parametric spectral estimation and Bayesian state estimation filters.

## Mental model

Knots here split into two families. Parametric spectral estimators (`ArModelEstimator`, `MusicEstimator`, `EspritEstimator`, `PisarenkoEstimator`, `PronyEstimator`) fit models to a signal and extract frequency content with super-resolution beyond what FFT length permits — they produce frequency/power descriptors, not modified signals. Bayesian filters (`ExtendedKalmanFilter`, `UnscentedKalmanFilter`, `ParticleFilter`) track time-varying hidden states through nonlinear dynamics and non-Gaussian noise. FFT-based spectral analysis lives in `pirn.domains.signal.spectral`.

## Source map

```
├── ar_model_estimator.py          ArModelEstimator          — autoregressive model PSD (Yule-Walker / Burg)
├── esprit_estimator.py            EspritEstimator           — subspace frequency estimator (ESPRIT algorithm)
├── extended_kalman_filter.py      ExtendedKalmanFilter      — EKF for nonlinear state-space models (linearized)
├── music_estimator.py             MusicEstimator            — MUSIC pseudospectrum for high-res frequency estimation
├── particle_filter.py             ParticleFilter            — sequential Monte Carlo for non-Gaussian state estimation
├── pisarenko_estimator.py         PisarenkoEstimator        — single-frequency subspace estimator
├── prony_estimator.py             PronyEstimator            — exponential sinusoid parameter estimation
├── unscented_kalman_filter.py     UnscentedKalmanFilter     — UKF for nonlinear models (sigma-point transform)
└── (MusicEstimator and EspritEstimator require n_signals < n_antennas/lags for subspace validity)
```

## Canonical pattern

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn.domains.signal.statistical.music_estimator import MusicEstimator

tapestry = Tapestry()

music = MusicEstimator(
    signal=Parameter("radar"),
    fs=1000,
    n_signals=3,       # number of sinusoidal components expected
    n_lags=20,         # autocorrelation matrix size
    _config=KnotConfig(id="music"),
)

result = tapestry.run(RunRequest(inputs={"radar": my_signal}))
freqs, pseudospectrum = result["music"]   # (freq_grid,), (freq_grid,)
```

```python
# Bayesian filter example
from pirn.domains.signal.statistical.unscented_kalman_filter import UnscentedKalmanFilter

ukf = UnscentedKalmanFilter(
    signal=Parameter("measurements"),
    state_transition_fn=my_transition,
    observation_fn=my_observation,
    Q=process_noise_cov,
    R=measurement_noise_cov,
    x0=initial_state,
    P0=initial_cov,
    _config=KnotConfig(id="ukf"),
)
```

## Anti-patterns

- **Using `MusicEstimator` when the number of signals is unknown.** MUSIC requires `n_signals` to be specified correctly; an incorrect value produces spurious or missing peaks. Use `ArModelEstimator` + model-order selection (AIC/BIC) when the number of components is uncertain.
- **Applying `ExtendedKalmanFilter` to highly nonlinear systems.** EKF linearizes around the current estimate; strong nonlinearity causes divergence. Use `UnscentedKalmanFilter` or `ParticleFilter`.
- **Using `ParticleFilter` without tuning particle count.** Too few particles → sample impoverishment and filter collapse; start with N ≥ 1000 and reduce only after profiling.

## Constraints and gotchas

- Parametric estimators (`MUSIC`, `ESPRIT`, `Pisarenko`) are designed for sinusoids in white noise; broadband spectra or colored noise require pre-whitening.
- `EspritEstimator` and `MusicEstimator` return frequency estimates as continuous values (not FFT bins), so their resolution is not limited by signal length.
- Bayesian filter knots (`EKF`, `UKF`, `ParticleFilter`) require user-supplied `state_transition_fn` and `observation_fn` callables (Python functions or other knots); they are not self-contained without these.
- `PronyEstimator` is sensitive to noise; it works best on near-noiseless signals or short windows.
- `ParticleFilter` is non-deterministic; set `random_seed` in `KnotConfig` metadata for reproducibility.
- Install with `pirn[signal]`.

## Quick reference

| Goal | Knot |
|---|---|
| Super-resolution frequency estimation | `MusicEstimator` or `EspritEstimator` |
| AR model / parametric PSD | `ArModelEstimator` |
| Single sinusoid frequency | `PisarenkoEstimator` |
| Exponential/damped sinusoid fit | `PronyEstimator` |
| Nonlinear state tracking (mild) | `ExtendedKalmanFilter` |
| Nonlinear state tracking (strong) | `UnscentedKalmanFilter` |
| Non-Gaussian / multi-modal posterior | `ParticleFilter` |

---

*See also: [signal AGENTIC_USE.md](../AGENTIC_USE.md)*
