Processes wearable sensor data — activity classification, ECG/PPG heart rate extraction, HRV analysis, sleep staging, glucose monitoring, and spirometry — does NOT handle BLE/USB device communication; ingest sensor data via DatabaseQuerySource or the appropriate file_formats connector.

## Mental model

Wearables knots accept time-series arrays or structured sensor records and emit derived metrics. Each knot wraps a single well-defined signal-processing or ML inference step. Knots are composable: the output of one knot (e.g., R-peak positions from `EcgRPeakDetector`) flows directly into the next (e.g., `HeartRateVariabilityAnalyzer`).

There are no quality gates in this sub-package. Signal quality validation is intentionally the responsibility of the calling pipeline: check sampling rate, missing-sample fraction, and amplitude range before wiring these knots. Knots that receive malformed or out-of-range input will raise `ValueError` with a descriptive message, not silently produce a result.

`SleepStager` and `AccelerometerActivityClassifier` load pre-trained ML models at init time. Model weights are bundled with `pirn[wearables]`; no external model registry or download step is required.

## Source map

```
pirn/domains/health/wearables/
├── accelerometer_activity_classifier.py  AccelerometerActivityClassifier  — classifies activity type from tri-axial accelerometer data
├── ecg_r_peak_detector.py                EcgRPeakDetector                 — detects R-peaks in ECG signal (Pan-Tompkins algorithm)
├── glucose_monitor_processor.py          GlucoseMonitorProcessor          — processes continuous glucose monitor (CGM) time series
├── heart_rate_variability_analyzer.py    HeartRateVariabilityAnalyzer     — computes time-domain and frequency-domain HRV metrics
├── ppg_heart_rate_extractor.py           PpgHeartRateExtractor            — extracts instantaneous heart rate from PPG signal
├── sleep_stager.py                       SleepStager                      — classifies sleep stages (Wake/N1/N2/N3/REM) from wrist actigraphy
├── spirometry_analyzer.py                SpirometryAnalyzer               — computes FEV1, FVC, FEV1/FVC from spirometry flow-volume data
└── step_counter.py                       StepCounter                      — counts steps from accelerometer magnitude signal
```

## Canonical pattern

Raw PPG stream → heart rate extract → HRV analyze:

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.wearables.ppg_heart_rate_extractor import PpgHeartRateExtractor
from pirn.domains.health.wearables.heart_rate_variability_analyzer import HeartRateVariabilityAnalyzer
from pirn.tapestry import Tapestry
import numpy as np

with Tapestry() as t:
    ppg_signal  = Parameter("ppg_signal", np.ndarray)   # shape (N,), units: a.u.
    sample_rate = Parameter("sample_rate", float)        # Hz, e.g. 64.0

    hr = PpgHeartRateExtractor(
        signal=ppg_signal,
        sample_rate=sample_rate,
        _config=KnotConfig(id="hr"),
    )
    HeartRateVariabilityAnalyzer(
        rr_intervals=hr,   # output: array of RR intervals in ms
        _config=KnotConfig(id="hrv"),
    )

result = await t.run(RunRequest(parameters={
    "ppg_signal": ppg_array,
    "sample_rate": 64.0,
}))
hrv_metrics = result.outputs["hrv"]
# hrv_metrics keys: sdnn, rmssd, pnn50, lf_power, hf_power, lf_hf_ratio
```

## Anti-patterns

**Wiring `HeartRateVariabilityAnalyzer` directly to raw ECG/PPG** — `HeartRateVariabilityAnalyzer` expects an array of RR intervals in milliseconds, not raw signal samples. Wire `EcgRPeakDetector` (for ECG) or `PpgHeartRateExtractor` (for PPG) first; passing raw samples produces nonsensical HRV metrics without raising an error.

**Passing mixed-unit accelerometer data to `SleepStager` or `AccelerometerActivityClassifier`** — both knots expect acceleration in units of gravitational acceleration (g). Raw ADC counts or m/s² values must be converted before being passed in. There is no unit-conversion step inside the knots; incorrect units produce confidently wrong classifications.

**Running `SpirometryAnalyzer` on volume-time instead of flow-volume data** — `SpirometryAnalyzer` expects a flow-volume curve (flow in L/s, volume in L). If your spirometer outputs a volume-time curve, differentiate it first. Passing volume-time data will produce FEV1/FVC values outside physiologically plausible ranges without raising an exception.

## Constraints and gotchas

- `SleepStager` requires at least 6 hours of continuous actigraphy data at ≥10 Hz sampling rate. Shorter windows or lower sampling rates raise `ValueError`.
- `EcgRPeakDetector` uses the Pan-Tompkins algorithm tuned for 250–1000 Hz sampling rates. At lower sampling rates (e.g., 64 Hz smartwatch ECG), peak detection accuracy degrades; consider resampling before processing.
- `GlucoseMonitorProcessor` handles gaps in CGM data (sensor dropouts, calibration windows) by linear interpolation up to a configurable maximum gap length. Gaps exceeding the threshold are left as `NaN` in the output array.
- `AccelerometerActivityClassifier` and `SleepStager` load bundled ML model weights on first instantiation, not at import time. The first `process()` call may be slow (100–500 ms) on cold start.
- All knots accept and return NumPy arrays or plain Python dicts; no MNE or domain-specific object types are used in this sub-package.
- Install: `pip install pirn[wearables]`

## Quick reference

| Task | How |
|---|---|
| Heart rate from PPG | `PpgHeartRateExtractor` |
| Heart rate from ECG | `EcgRPeakDetector` → compute HR from RR intervals |
| HRV metrics | `EcgRPeakDetector` or `PpgHeartRateExtractor` → `HeartRateVariabilityAnalyzer` |
| Activity classification | `AccelerometerActivityClassifier` (tri-axial accel in g) |
| Step count | `StepCounter` (tri-axial or single-axis accel) |
| Sleep staging | `SleepStager` (≥6 h actigraphy at ≥10 Hz) |
| CGM processing | `GlucoseMonitorProcessor` (handles gaps, computes AGP metrics) |
| Spirometry (FEV1/FVC) | `SpirometryAnalyzer` (flow-volume curve input) |

*See also: [health AGENTIC_USE.md](../AGENTIC_USE.md)*
