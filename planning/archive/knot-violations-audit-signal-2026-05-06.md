# Knot Design Rules Audit Report

**Scan Date:** 2026-05-06  
**Method:** Automated AST scan, all rules R1-R11 + Security

## Legend

| Column | Rule | Details |
|--------|------|---------|
| R1 | `__init__` body is ONLY `super().__init__(...)` | No validation, assignments, or logic |
| R2 | Every `__init__` param (except `_config`, `**kwargs`) appears by same name in `process()` | Ensures direct testability |
| R3 | No `raise` statements in `__init__` | All validation deferred to `process()` |
| R4 | No `self._x` assignments storing inputs | Inputs arrive fresh in `process()` |
| R5 | No `@property` exposing stored inputs or derived strings | Computed values via private helpers only |
| R6 | Opaque resources use a dedicated vending Knot, not passed directly | Live connections/sessions cannot travel the graph |
| R7 | `__init__` params use Knot types or `Knot \| scalar` — NOT plain scalars | Ensures graph wiring and lineage |
| R8 | If inherits `SubTapestry`: `process()` calls `self._run_inner()` | N/A for plain `Knot`/`Source`/`Sink` |
| R9 | Quality assessment Knots returning `QualityReport` use `*Check` suffix, not `*Gate` | N/A if not a quality assessment Knot |
| R10-Algo | Module docstring contains `Algorithm:` section | Step-by-step description |
| R10-Math | Module docstring contains `Math:` section | Always required — N/A confirmed only after reading `process()` |
| R10-Refs | Module docstring contains `References:` section | N/A if entirely pirn-native |
| Sec | Any `hashlib.md5()` call includes `usedforsecurity=False` | N/A if no md5 usage |
| Step11 | Tests call `process()` directly with plain values under `tests/unit/` | Not just via Tapestry.run() |
| Step12 | All applicable rules pass AND Step11 passes | Ready for ruff/pyright/pytest |

**Cell values:** `[x]` = compliant · `[ ]` = violation · `N/A` = rule does not apply

---

## Audit Table

### Group 1 — adaptive/affine_projection_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/adaptive/affine_projection_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 2 — adaptive/anc_pipeline.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/adaptive/anc_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 3 — adaptive/echo_canceller.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/adaptive/echo_canceller.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 4 — adaptive/kalman_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/adaptive/kalman_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 5 — adaptive/lms_adaptive_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/adaptive/lms_adaptive_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 6 — adaptive/nlms_adaptive_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/adaptive/nlms_adaptive_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 7 — adaptive/rls_adaptive_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/adaptive/rls_adaptive_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 8 — adaptive/subband_adaptive_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/adaptive/subband_adaptive_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 9 — audio/audio_augmentation_pipeline.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/audio/audio_augmentation_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 10 — audio/audio_denoiser.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/audio/audio_denoiser.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 11 — audio/audio_feature_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/audio/audio_feature_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 12 — audio/audio_file_ingestor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/audio/audio_file_ingestor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 13 — audio/audio_resampler.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/audio/audio_resampler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 14 — audio/beat_tracker.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/audio/beat_tracker.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 15 — audio/mel_spectrogram_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/audio/mel_spectrogram_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 16 — audio/mfcc_extractor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/audio/mfcc_extractor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 17 — audio/music_information_retriever.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/audio/music_information_retriever.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 18 — audio/onset_detector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/audio/onset_detector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 19 — audio/pitch_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/audio/pitch_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 20 — audio/speaker_diarization_pipeline.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/audio/speaker_diarization_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 21 — audio/vad_detector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/audio/vad_detector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 22 — beamforming/beamformer_music.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/beamforming/beamformer_music.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 23 — beamforming/beamformer_mvdr.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/beamforming/beamformer_mvdr.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 24 — beamforming/delay_and_sum_beamformer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/beamforming/delay_and_sum_beamformer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 25 — filters/allpass_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/allpass_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 26 — filters/band_pass_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/band_pass_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 27 — filters/band_stop_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/band_stop_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 28 — filters/bandpass_filter_bank.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/bandpass_filter_bank.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 29 — filters/bessel_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/bessel_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 30 — filters/butterworth_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/butterworth_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 31 — filters/causal_realtime_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/causal_realtime_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 32 — filters/chebyshev_type1_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/chebyshev_type1_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 33 — filters/chebyshev_type2_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/chebyshev_type2_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 34 — filters/comb_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/comb_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 35 — filters/elliptic_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/elliptic_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 36 — filters/fir_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/fir_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 37 — filters/fir_parks_mcclellan_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/fir_parks_mcclellan_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 38 — filters/fir_window_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/fir_window_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 39 — filters/high_pass_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/high_pass_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 40 — filters/iir_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/iir_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 41 — filters/kalman_smoother.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/kalman_smoother.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 42 — filters/low_pass_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/low_pass_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 43 — filters/matched_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/matched_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 44 — filters/median_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/median_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 45 — filters/notch_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/notch_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 46 — filters/polyphase_decimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/polyphase_decimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 47 — filters/savitzky_golay_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/savitzky_golay_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 48 — filters/wiener_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/wiener_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 49 — filters/zero_phase_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/filters/zero_phase_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 50 — nonlinear/correlation_dimension_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/nonlinear/correlation_dimension_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 51 — nonlinear/entropy_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/nonlinear/entropy_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 52 — nonlinear/hurst_exponent_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/nonlinear/hurst_exponent_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 53 — nonlinear/lyapunov_exponent_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/nonlinear/lyapunov_exponent_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 54 — nonlinear/permutation_entropy_calculator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/nonlinear/permutation_entropy_calculator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 55 — nonlinear/recurrence_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/nonlinear/recurrence_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 56 — nonlinear/sample_entropy_calculator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/nonlinear/sample_entropy_calculator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 57 — resampling/arbitrary_resampler_pipeline.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/resampling/arbitrary_resampler_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 58 — resampling/clock_drift_corrector.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/resampling/clock_drift_corrector.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 59 — resampling/decimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/resampling/decimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 60 — resampling/downsampler.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/resampling/downsampler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 61 — resampling/fractional_delay_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/resampling/fractional_delay_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 62 — resampling/interpolator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/resampling/interpolator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 63 — resampling/multi_rate_fusion_pipeline.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/resampling/multi_rate_fusion_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 64 — resampling/polyphase_resampler.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/resampling/polyphase_resampler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 65 — resampling/rational_resampler_pipeline.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/resampling/rational_resampler_pipeline.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 66 — resampling/streaming_buffer_manager.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/resampling/streaming_buffer_manager.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 67 — resampling/time_synchronizer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/resampling/time_synchronizer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 68 — resampling/upsampler.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/resampling/upsampler.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 69 — separation/dictionary_learner.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/separation/dictionary_learner.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 70 — separation/ica_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/separation/ica_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 71 — separation/ica_robust_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/separation/ica_robust_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 72 — separation/nmf_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/separation/nmf_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 73 — separation/pca_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/separation/pca_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 74 — separation/sparse_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/separation/sparse_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 75 — separation/ssa_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/separation/ssa_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 76 — spectral/bartlett_psd_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/bartlett_psd_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 77 — spectral/bispectrum_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/bispectrum_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 78 — spectral/cepstrum_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/cepstrum_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 79 — spectral/chirplet_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/chirplet_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 80 — spectral/cross_spectrum_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/cross_spectrum_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 81 — spectral/fft_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/fft_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 82 — spectral/hilbert_transformer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/hilbert_transformer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 83 — spectral/ifft_reconstructor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/ifft_reconstructor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 84 — spectral/istft_reconstructor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/istft_reconstructor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 85 — spectral/multitaper_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/multitaper_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 86 — spectral/periodogram_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/periodogram_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 87 — spectral/spectrogram_renderer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/spectrogram_renderer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 88 — spectral/stft_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/stft_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 89 — spectral/welch_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/spectral/welch_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 90 — statistical/ar_model_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/statistical/ar_model_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 91 — statistical/esprit_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/statistical/esprit_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 92 — statistical/extended_kalman_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/statistical/extended_kalman_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 93 — statistical/music_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/statistical/music_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 94 — statistical/particle_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/statistical/particle_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 95 — statistical/pisarenko_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/statistical/pisarenko_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 96 — statistical/prony_estimator.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/statistical/prony_estimator.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 97 — statistical/unscented_kalman_filter.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/statistical/unscented_kalman_filter.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 98 — wavelets/cwt_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/wavelets/cwt_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 99 — wavelets/dwpt_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/wavelets/dwpt_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 100 — wavelets/dwt_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/wavelets/dwt_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 101 — wavelets/eemd_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/wavelets/eemd_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 102 — wavelets/emd_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/wavelets/emd_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 103 — wavelets/idwt_reconstructor.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/wavelets/idwt_reconstructor.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 104 — wavelets/multiresolution_analyzer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/wavelets/multiresolution_analyzer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 105 — wavelets/swt_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/wavelets/swt_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 106 — wavelets/vmd_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/wavelets/vmd_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 107 — wavelets/wavelet_denoiser.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/wavelets/wavelet_denoiser.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |

### Group 108 — wavelets/wavelet_packet_decomposer.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/signal/wavelets/wavelet_packet_decomposer.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | [x] | [x] | N/A | [x] | [x] |
