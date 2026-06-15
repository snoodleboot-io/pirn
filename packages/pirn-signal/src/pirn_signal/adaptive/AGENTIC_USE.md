Adaptive filters that update coefficients online from incoming data — used for noise cancellation, echo removal, equalization, and system identification.

## Mental model

Every knot here maintains a set of filter coefficients that evolve as data flows through; they are not designed offline. The canonical workflow is: provide a `primary` input (signal + noise) and a `reference` input (correlated with noise), and the adaptive filter converges to subtract the noise component. `LmsAdaptiveFilter` (gradient descent) and `NlmsAdaptiveFilter` (normalized step) are the workhorse pair. `KalmanFilter` treats the coefficient vector as a state to be estimated. For static IIR or FIR filters with fixed coefficients, use `pirn_signal.filters`.

## Source map

```
├── affine_projection_filter.py  AffineProjectionFilter  — fast convergence via projection onto affine subspace
├── anc_pipeline.py              AncPipeline             — active noise cancellation end-to-end pipeline
├── echo_canceller.py            EchoCanceller           — acoustic echo cancellation (AEC) for full-duplex
├── kalman_filter.py             KalmanFilter            — linear state-space adaptive filter (Kalman gain)
├── lms_adaptive_filter.py       LmsAdaptiveFilter       — least mean squares adaptive filter
├── nlms_adaptive_filter.py      NlmsAdaptiveFilter      — normalized LMS for variable-power inputs
├── rls_adaptive_filter.py       RlsAdaptiveFilter       — recursive least squares (fast convergence, higher cost)
├── subband_adaptive_filter.py   SubbandAdaptiveFilter   — adaptive filtering per frequency sub-band
└── (AncPipeline composes LmsAdaptiveFilter + secondary path model)
```

## Canonical pattern

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn_signal.adaptive.nlms_adaptive_filter import NlmsAdaptiveFilter

tapestry = Tapestry()

# primary = speech + noise; reference = noise reference microphone
filtered = NlmsAdaptiveFilter(
    primary=Parameter("primary"),
    reference=Parameter("reference"),
    fs=16000,
    filter_order=64,
    step_size=0.1,
    _config=KnotConfig(id="nlms"),
)

result = tapestry.run(RunRequest(inputs={
    "primary": primary_signal,
    "reference": reference_signal,
}))
clean_speech = result["nlms"]
```

## Anti-patterns

- **Using `LmsAdaptiveFilter` for highly non-stationary signals.** LMS has slow convergence; use `RlsAdaptiveFilter` (faster convergence at higher compute cost) or `AffineProjectionFilter` for colored inputs.
- **Wiring `KalmanFilter` without tuning `Q` and `R`.** Poorly tuned process noise (`Q`) and measurement noise (`R`) covariances produce a filter that either diverges or ignores the data entirely.
- **Using `AncPipeline` when reference is not acoustically coherent with noise.** The pipeline assumes the reference is correlated with noise at the primary mic; uncorrelated reference will cause divergence.

## Constraints and gotchas

- `LmsAdaptiveFilter` and `NlmsAdaptiveFilter` require `step_size` tuning; too large → instability, too small → slow convergence.
- `RlsAdaptiveFilter` has O(N²) complexity per sample (N = filter order); keep `filter_order` small for real-time use.
- `EchoCanceller` requires the far-end (loudspeaker) signal as `reference`; it cannot cancel echo without it.
- `SubbandAdaptiveFilter` speeds up convergence for colored noise but introduces sub-band delay; check latency requirements.
- Adaptive filters are stateful — they carry coefficient state across tapestry `run` calls if the knot instance is reused, which is intentional for streaming but may surprise in batch contexts.
- Install with `pirn-signal[signal]`.

## Quick reference

| Goal | Knot |
|---|---|
| Basic noise cancellation | `NlmsAdaptiveFilter` |
| Acoustic echo cancellation | `EchoCanceller` |
| Active noise cancellation | `AncPipeline` |
| Fast convergence | `RlsAdaptiveFilter` or `AffineProjectionFilter` |
| State-space / Kalman approach | `KalmanFilter` |
| Colored noise, sub-band | `SubbandAdaptiveFilter` |

---

*See also: [signal AGENTIC_USE.md](../AGENTIC_USE.md)*
