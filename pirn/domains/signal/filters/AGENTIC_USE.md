Frequency-domain and time-domain digital filters — shape, attenuate, or smooth a signal without changing its sample rate.

## Mental model

Every knot here receives a `signal` array and `fs` (Hz) and returns a filtered signal of the same length and sample rate. Filter design is baked into the knot; pass cutoff frequencies and order as `Parameter` values. Choose the design by the roll-off characteristic you need (Butterworth → maximally flat; Chebyshev → steeper but rippled; Elliptic → steepest; Bessel → best phase; FIR → linear phase; Kalman → optimal if you have a noise model). For zero-phase offline use, prefer `ZeroPhaseFilter`; for real-time, use `CausalRealtimeFilter`.

## Source map

```
├── allpass_filter.py            AllpassFilter            — shifts phase without altering magnitude
├── bandpass_filter_bank.py      BandpassFilterBank       — applies a bank of bandpass filters in parallel
├── band_pass_filter.py          BandPassFilter           — passes frequencies within [low, high] cutoff
├── band_stop_filter.py          BandStopFilter           — rejects frequencies within [low, high] cutoff
├── bessel_filter.py             BesselFilter             — maximally linear phase IIR lowpass/highpass
├── butterworth_filter.py        ButterworthFilter        — maximally flat magnitude IIR filter
├── causal_realtime_filter.py    CausalRealtimeFilter     — single-pass causal filter safe for streaming
├── chebyshev_type1_filter.py    ChebyshevType1Filter     — equiripple passband, monotone stopband
├── chebyshev_type2_filter.py    ChebyshevType2Filter     — monotone passband, equiripple stopband
├── comb_filter.py               CombFilter               — enhances or cancels harmonically spaced frequencies
├── elliptic_filter.py           EllipticFilter           — equiripple in both bands, steepest roll-off
├── fir_filter.py                FirFilter                — generic FIR with user-supplied coefficients
├── fir_parks_mcclellan_filter.py FirParksMcClellanFilter — equiripple FIR via Parks-McClellan (Remez)
├── fir_window_filter.py         FirWindowFilter          — windowed-sinc FIR (Hamming, Hann, Blackman…)
├── high_pass_filter.py          HighPassFilter           — passes frequencies above cutoff
├── iir_filter.py                IirFilter                — generic IIR with user-supplied b/a coefficients
├── kalman_smoother.py           KalmanSmoother           — RTS smoother for Gaussian noise reduction
├── low_pass_filter.py           LowPassFilter            — passes frequencies below cutoff
├── matched_filter.py            MatchedFilter            — correlates signal against a known template
├── median_filter.py             MedianFilter             — nonlinear rank-order filter, removes impulse noise
├── notch_filter.py              NotchFilter              — rejects a single narrow frequency (e.g. 50/60 Hz)
├── polyphase_decimator.py       PolyphaseDecimator       — filters then decimates in one efficient operation
├── savitzky_golay_filter.py     SavitzkyGolayFilter      — polynomial least-squares smoothing
├── wiener_filter.py             WienerFilter             — optimal linear filter given signal/noise PSDs
└── zero_phase_filter.py         ZeroPhaseFilter          — forward-backward filtering for zero phase distortion
```

## Canonical pattern

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn.domains.signal.filters.butterworth_filter import ButterworthFilter
from pirn.domains.signal.filters.zero_phase_filter import ZeroPhaseFilter

tapestry = Tapestry()

# Low-pass at 100 Hz, then zero-phase it for offline use
lp = ButterworthFilter(
    signal=Parameter("raw"),
    fs=1000,
    cutoff=100.0,
    order=4,
    filter_type="low",
    _config=KnotConfig(id="lp"),
)
zp = ZeroPhaseFilter(
    signal=lp.output,
    _config=KnotConfig(id="zp"),
)

result = tapestry.run(RunRequest(inputs={"raw": my_signal}))
filtered = result["zp"]
```

## Anti-patterns

- **Resampling inside a filter knot.** Filters preserve sample rate. If you need a lower rate, run `PolyphaseDecimator` (which integrates anti-aliasing) or route through `pirn.domains.signal.resampling` afterward.
- **Using `ZeroPhaseFilter` in streaming.** Forward-backward requires the full buffer; use `CausalRealtimeFilter` for online/streaming pipelines.
- **Designing a notch with `BandStopFilter` and a wide stopband.** `NotchFilter` is purpose-built, has better Q control, and avoids unintended passband distortion.

## Constraints and gotchas

- All cutoff frequencies are in Hz; `fs` must match the signal's actual sample rate or results will be wrong silently.
- High-order IIR filters (order > 8) can become numerically unstable; prefer second-order sections (SOS) internally — the knots do this automatically, but very high orders still risk instability.
- `KalmanSmoother` requires `process_noise` and `measurement_noise` variance parameters; they have no sensible default.
- `MatchedFilter` output length equals `len(signal) + len(template) - 1` (full convolution); trim if needed.
- `MedianFilter` is nonlinear — it does not have a frequency response; avoid when linear phase is required.
- Install with `pirn[signal]`.

## Quick reference

| Goal | Knot |
|---|---|
| Remove DC / low drift | `HighPassFilter(cutoff=0.5)` |
| Anti-alias before decimation | `LowPassFilter` or `PolyphaseDecimator` |
| Kill 50/60 Hz hum | `NotchFilter(freq=50)` |
| Zero-phase offline smoothing | `ZeroPhaseFilter` wrapping any IIR |
| Polynomial smoothing | `SavitzkyGolayFilter` |
| Real-time single-pass | `CausalRealtimeFilter` |
| Steepest roll-off | `EllipticFilter` |
| Best phase linearity | `BesselFilter` |
| Guaranteed linear phase | `FirWindowFilter` or `FirParksMcClellanFilter` |
| Noise model available | `WienerFilter` or `KalmanSmoother` |

---

*See also: [signal AGENTIC_USE.md](../AGENTIC_USE.md)*
