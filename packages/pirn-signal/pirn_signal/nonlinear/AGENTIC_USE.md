Nonlinear dynamics and chaos analysis — quantify complexity, fractal dimension, and sensitivity to initial conditions in a signal.

## Mental model

Knots here treat a signal as a realization of a nonlinear dynamical system and compute scalar descriptors that characterize that system's behavior. `EntropyEstimator` and `PermutationEntropyCalculator` measure information content and regularity. `LyapunovExponentEstimator` and `CorrelationDimensionEstimator` characterize chaos and fractal geometry. `HurstExponentEstimator` measures long-range dependence. `RecurrenceAnalyzer` builds a recurrence plot for visual and quantitative inspection of phase-space structure. Linear spectral analysis belongs in `pirn_signal.spectral`.

## Source map

```
├── correlation_dimension_estimator.py  CorrelationDimensionEstimator  — fractal dimension via correlation integral
├── entropy_estimator.py                EntropyEstimator               — approximate entropy (ApEn) estimation
├── hurst_exponent_estimator.py         HurstExponentEstimator         — long-range dependence (R/S analysis)
├── lyapunov_exponent_estimator.py      LyapunovExponentEstimator      — largest Lyapunov exponent (chaos measure)
├── permutation_entropy_calculator.py   PermutationEntropyCalculator   — ordinal pattern entropy (fast, robust)
├── recurrence_analyzer.py              RecurrenceAnalyzer             — recurrence plot and RQA measures
├── sample_entropy_calculator.py        SampleEntropyCalculator        — sample entropy (less biased than ApEn)
└── (all knots return scalar or 2-D array descriptors, not modified signals)
```

## Canonical pattern

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn_signal.nonlinear.permutation_entropy_calculator import PermutationEntropyCalculator
from pirn_signal.nonlinear.hurst_exponent_estimator import HurstExponentEstimator

tapestry = Tapestry()

pe = PermutationEntropyCalculator(
    signal=Parameter("ts"),
    order=5,
    delay=1,
    normalize=True,
    _config=KnotConfig(id="pe"),
)
hurst = HurstExponentEstimator(
    signal=Parameter("ts"),
    method="rs",
    _config=KnotConfig(id="hurst"),
)

result = tapestry.run(RunRequest(inputs={"ts": my_time_series}))
entropy_value = result["pe"]    # scalar in [0, 1]
H = result["hurst"]             # Hurst exponent scalar
```

## Anti-patterns

- **Using `EntropyEstimator` (ApEn) on short signals.** ApEn is biased for N < 1000 samples; use `SampleEntropyCalculator` which has less length-dependent bias.
- **Interpreting `LyapunovExponentEstimator` results without sufficient data.** Reliable Lyapunov exponent estimation requires long, clean, stationary time series (typically N > 10 000); noisy or short signals yield unreliable values.
- **Running `CorrelationDimensionEstimator` without embedding parameter selection.** Embedding dimension and delay must be chosen first (e.g. via false nearest neighbors and mutual information) or the dimension estimate is meaningless.

## Constraints and gotchas

- `RecurrenceAnalyzer` builds an N×N matrix; for N > 5000 this becomes large (25 M elements); use `threshold` carefully to control density.
- All estimators assume stationarity; apply them to stationary segments rather than long non-stationary recordings.
- `LyapunovExponentEstimator` uses the Rosenstein algorithm by default; set `method="wolf"` for the Wolf algorithm (slower, requires longer data).
- `HurstExponentEstimator` with `method="dfa"` (detrended fluctuation analysis) is more robust to non-stationarity than `"rs"`.
- Outputs are scalar descriptors or small arrays, not signals; they cannot be fed back into signal-domain knots.
- Install with `pirn-signal[signal]`.

## Quick reference

| Goal | Knot |
|---|---|
| Regularity / complexity | `SampleEntropyCalculator` |
| Fast complexity measure | `PermutationEntropyCalculator` |
| Chaos detection | `LyapunovExponentEstimator` |
| Fractal dimension | `CorrelationDimensionEstimator` |
| Long-range dependence | `HurstExponentEstimator` |
| Phase-space structure | `RecurrenceAnalyzer` |

---

*See also: [signal AGENTIC_USE.md](../AGENTIC_USE.md)*
