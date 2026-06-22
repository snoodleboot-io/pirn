Sample rate conversion — change the sample rate of a signal by integer, rational, or arbitrary factors.

## Mental model

Knots here consume a signal at one `fs` and emit it at another. They are rate-changing primitives: `Decimator` and `Downsampler` reduce rate, `Interpolator` and `Upsampler` increase it, and `PolyphaseResampler` / `RationalResamplerPipeline` handle rational ratios efficiently. `ArbitraryResamplerPipeline` handles non-integer ratios (e.g. 44100 → 22050 or 48000 → 16000). Anti-aliasing filtering is built in to all downsampling knots. If additional content filtering is needed after resampling (e.g. aggressive bandlimiting), wire in a knot from `pirn_signal.filters` afterward.

## Source map

```
├── arbitrary_resampler_pipeline.py  ArbitraryResamplerPipeline  — resamples to any target fs (non-integer ratio)
├── clock_drift_corrector.py         ClockDriftCorrector         — corrects gradual clock drift between two streams
├── decimator.py                     Decimator                   — downsamples by integer factor M (with anti-alias)
├── downsampler.py                   Downsampler                 — discards samples by integer factor (no filtering)
├── fractional_delay_filter.py       FractionalDelayFilter       — shifts signal by a sub-sample delay
├── interpolator.py                  Interpolator                — upsamples by integer factor L (with anti-alias)
├── multi_rate_fusion_pipeline.py    MultiRateFusionPipeline     — aligns and fuses streams at different rates
├── polyphase_resampler.py           PolyphaseResampler          — efficient polyphase rational resampling
├── rational_resampler_pipeline.py   RationalResamplerPipeline   — L/M rational resampling with anti-aliasing
├── streaming_buffer_manager.py      StreamingBufferManager      — manages input/output buffers for streaming resamplers
├── time_synchronizer.py             TimeSynchronizer            — resamples multiple signals to a common time grid
├── upsampler.py                     Upsampler                   — inserts zeros by integer factor (no filtering)
└── (PolyphaseDecimator in filters/ also performs combined filter+decimate)
```

## Canonical pattern

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn_signal.resampling.rational_resampler_pipeline import RationalResamplerPipeline

tapestry = Tapestry()

# Resample from 48000 Hz to 16000 Hz (ratio 1/3)
resampled = RationalResamplerPipeline(
    signal=Parameter("audio_48k"),
    fs_in=48000,
    fs_out=16000,
    _config=KnotConfig(id="resampled"),
)

result = tapestry.run(RunRequest(inputs={"audio_48k": my_signal}))
signal_16k = result["resampled"]
```

## Anti-patterns

- **Using `Downsampler` without pre-filtering.** `Downsampler` simply discards samples — it has no anti-aliasing filter. Always use `Decimator` or `RationalResamplerPipeline` when downsampling to avoid aliasing.
- **Using `Upsampler` for final output.** `Upsampler` inserts zeros (spectral images); follow it with `Interpolator` or an `LowPassFilter` to remove the images.
- **Chaining multiple decimators instead of one rational resampler.** Multiple passes accumulate quantization and filtering artifacts; one `RationalResamplerPipeline` is more accurate.

## Constraints and gotchas

- All output knots report their actual `fs_out` on the output metadata; wire downstream knots using this, not a hardcoded value.
- `ClockDriftCorrector` requires a reference signal or an estimated drift rate (ppm); it does not auto-detect drift.
- `FractionalDelayFilter` introduces a small fixed group delay equal to the filter half-length; compensate if absolute timing matters.
- `StreamingBufferManager` must be configured with the same chunk size as the upstream source; mismatched chunk sizes cause buffer overrun errors.
- `MultiRateFusionPipeline` resamples all inputs to the highest `fs` present by default; override with `target_fs`.
- Install with `pirn-signal[signal]`.

## Quick reference

| Goal | Knot |
|---|---|
| Halve sample rate (integer) | `Decimator(factor=2)` |
| Double sample rate (integer) | `Interpolator(factor=2)` |
| Arbitrary ratio (e.g. 44100→22050) | `ArbitraryResamplerPipeline` |
| Rational ratio (e.g. 48000→16000) | `RationalResamplerPipeline` |
| Align two differently-clocked streams | `TimeSynchronizer` |
| Correct clock drift | `ClockDriftCorrector` |
| Sub-sample delay correction | `FractionalDelayFilter` |
| Fuse multi-rate sensor streams | `MultiRateFusionPipeline` |

---

*See also: [signal AGENTIC_USE.md](../AGENTIC_USE.md)*
