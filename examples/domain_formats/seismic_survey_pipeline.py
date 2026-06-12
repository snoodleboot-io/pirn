"""Seismic survey analysis pipeline — static DAG over SEG-Y trace data.

Loads a set of synthetic SEG-Y traces, normalises amplitude and geometry,
then runs four independent analysers in parallel before assembling a survey
report.

Pipeline shape:

    TraceLoader ──► TraceNormaliser ──┬──► FrequencyAnalyser   ──┐
                                      ├──► AmplitudeScorer     ──┤
                                      ├──► VelocityEstimator   ──┼──► SurveyReport
                                      └──► HorizonPicker       ──┘

Working with real SEG-Y data:

    Replace ``_synthetic_traces()`` with bytes decoded by ``SegyFormat``:

        from pirn.connectors.file_formats.segy_format import SegyFormat

        fmt = SegyFormat(sample_rate=2000)
        traces = await fmt.decode(segy_bytes)   # one record per trace

    Each trace record has: trace_index (int), header (dict), data (float32 bytes).
    ``TraceLoader`` accepts that list directly.

Run with:
    uv run python examples/domain_formats/seismic_survey_pipeline.py
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import random
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- data models


@dataclass
class TraceRecord:
    """Matches the record schema emitted by ``SegyFormat.decode()``."""

    trace_index: int
    header: dict[str, Any]
    data: bytes


@dataclass
class NormalisedSurvey:
    n_traces: int
    sample_rate_us: int
    n_samples: int
    traces: list[list[float]]
    cdp_x: list[float]
    cdp_y: list[float]
    offset_range: tuple[float, float]


@dataclass
class FrequencySpectrum:
    dominant_hz: float
    bandwidth_hz: float
    peak_power_db: float
    noise_floor_db: float
    signal_to_noise: float


@dataclass
class AmplitudeStats:
    rms_amplitude: float
    peak_amplitude: float
    p10: float
    p90: float
    dynamic_range_db: float


@dataclass
class VelocityModel:
    interval_velocities: list[tuple[float, float]]
    vrms_surface: float
    vrms_target: float
    two_way_time_ms: float


@dataclass
class HorizonPick:
    name: str
    two_way_time_ms: float
    avg_amplitude: float
    confidence: float
    n_traces_picked: int


@dataclass
class SurveyResult:
    survey_name: str
    n_traces: int
    frequency: FrequencySpectrum
    amplitude: AmplitudeStats
    velocity: VelocityModel
    horizons: list[HorizonPick]

    def summary(self) -> str:
        hz = f"{self.frequency.dominant_hz:.0f} Hz"
        snr = f"{self.frequency.signal_to_noise:.1f} dB"
        rms = f"{self.amplitude.rms_amplitude:.3f}"
        hrz = "  ".join(
            f"{h.name}@{h.two_way_time_ms:.0f}ms({h.confidence:.0%})" for h in self.horizons
        )
        return (
            f"[{self.survey_name}] {self.n_traces} traces\n"
            f"  Frequency : {hz} dominant · SNR {snr}\n"
            f"  Amplitude : RMS={rms} · "
            f"dynamic range {self.amplitude.dynamic_range_db:.0f} dB\n"
            f"  Velocity  : Vrms(target)={self.velocity.vrms_target:.0f} m/s · "
            f"TWT={self.velocity.two_way_time_ms:.0f} ms\n"
            f"  Horizons  : {hrz}"
        )


# ----------------------------------------------------------------- synthetic data


def _rng(survey: str, extra: str = "") -> random.Random:
    key = f"{survey}|{extra}"
    seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _synthetic_traces(
    survey_name: str, n_traces: int = 120, n_samples: int = 500
) -> list[TraceRecord]:
    """Return synthetic trace records shaped like SegyFormat output."""
    rng = _rng(survey_name)
    records: list[TraceRecord] = []
    for i in range(n_traces):
        # Ricker wavelet with noise
        peak_t = rng.randint(80, 200)
        amplitude = rng.uniform(0.5, 2.0)
        values: list[float] = []
        for t in range(n_samples):
            dt = t - peak_t
            ricker = (
                amplitude
                * (1 - 2 * (math.pi * 30 * dt * 0.002) ** 2)
                * math.exp(-((math.pi * 30 * dt * 0.002) ** 2))
            )
            noise = rng.gauss(0, 0.05 * amplitude)
            values.append(ricker + noise)
        data = struct.pack(f">{n_samples}f", *values)
        header = {
            "CDP": i + 1,
            "OFFSET": rng.randint(100, 3000),
            "CDP_X": int(rng.uniform(400000, 400500) * 10),
            "CDP_Y": int(rng.uniform(6500000, 6500500) * 10),
            "DELRT": 0,
            "DT": 2000,
            "NS": n_samples,
        }
        records.append(TraceRecord(trace_index=i, header=header, data=data))
    return records


# ----------------------------------------------------------------- knots


class TraceLoader(Knot):
    """Validates a list of trace records and passes them downstream.

    In production, this knot would call ``SegyFormat.decode(payload)``
    to materialise trace records from raw bytes.
    """

    async def process(
        self, traces: list[TraceRecord], survey_name: str, **_: Any
    ) -> list[TraceRecord]:
        if not traces:
            raise ValueError(f"TraceLoader: survey '{survey_name}' has no traces")
        return traces


class TraceNormaliser(Knot):
    """Decodes float32 sample bytes, extracts geometry, and normalises amplitudes.

    Scales each trace to zero-mean unit-variance and extracts CDP coordinates
    and offsets from the trace header dictionary.
    """

    async def process(self, traces: list[TraceRecord], **_: Any) -> NormalisedSurvey:
        all_traces: list[list[float]] = []
        cdp_x: list[float] = []
        cdp_y: list[float] = []
        offsets: list[float] = []

        n_samples = 0
        sample_rate = 2000

        for rec in traces:
            n = len(rec.data) // 4
            if n == 0:
                continue
            raw = list(struct.unpack(f">{n}f", rec.data))
            n_samples = n
            mu = sum(raw) / len(raw)
            variance = sum((v - mu) ** 2 for v in raw) / len(raw)
            std = math.sqrt(variance) or 1.0
            normalised = [(v - mu) / std for v in raw]
            all_traces.append(normalised)

            hdr = rec.header
            scale = hdr.get("SourceMeasurement", 1) or 1
            cdp_x.append(hdr.get("CDP_X", 0) / (abs(scale) or 100))
            cdp_y.append(hdr.get("CDP_Y", 0) / (abs(scale) or 100))
            offsets.append(float(hdr.get("OFFSET", 0)))
            sample_rate = int(hdr.get("DT", 2000))

        min_offset = min(offsets) if offsets else 0.0
        max_offset = max(offsets) if offsets else 0.0

        return NormalisedSurvey(
            n_traces=len(all_traces),
            sample_rate_us=sample_rate,
            n_samples=n_samples,
            traces=all_traces,
            cdp_x=cdp_x,
            cdp_y=cdp_y,
            offset_range=(min_offset, max_offset),
        )


class FrequencyAnalyser(Knot):
    """Estimates dominant frequency and SNR from trace amplitude spectra.

    Uses a simple DFT approximation over the first 256 samples; a real
    implementation would use scipy.fft on the full float32 array.
    """

    async def process(self, survey: NormalisedSurvey, **_: Any) -> FrequencySpectrum:
        if not survey.traces:
            raise ValueError("FrequencyAnalyser: survey has no traces")

        dt_s = survey.sample_rate_us * 1e-6
        n = min(256, survey.n_samples)
        stack = [sum(t[i] for t in survey.traces) / survey.n_traces for i in range(n)]

        max_power = 0.0
        dominant_bin = 1
        power_spectrum: list[float] = []
        for k in range(1, n // 2):
            re = sum(stack[t] * math.cos(2 * math.pi * k * t / n) for t in range(n))
            im = sum(stack[t] * math.sin(2 * math.pi * k * t / n) for t in range(n))
            power = math.sqrt(re**2 + im**2)
            power_spectrum.append(power)
            if power > max_power:
                max_power = power
                dominant_bin = k

        nyquist = 1.0 / (2 * dt_s)
        dominant_hz = dominant_bin * nyquist / (n // 2)

        half_power = max_power * 0.707
        bw_bins = sum(1 for p in power_spectrum if p >= half_power)
        bandwidth_hz = bw_bins * nyquist / (n // 2)

        noise_idx = len(power_spectrum) * 3 // 4
        noise_floor = sum(power_spectrum[noise_idx:]) / max(len(power_spectrum) - noise_idx, 1)
        snr_db = 20 * math.log10(max_power / noise_floor) if noise_floor > 0 else 0.0
        peak_db = 20 * math.log10(max_power) if max_power > 0 else 0.0
        floor_db = 20 * math.log10(noise_floor) if noise_floor > 0 else 0.0

        return FrequencySpectrum(
            dominant_hz=round(dominant_hz, 1),
            bandwidth_hz=round(bandwidth_hz, 1),
            peak_power_db=round(peak_db, 1),
            noise_floor_db=round(floor_db, 1),
            signal_to_noise=round(snr_db, 1),
        )


class AmplitudeScorer(Knot):
    """Computes RMS, peak amplitude, percentiles, and dynamic range."""

    async def process(self, survey: NormalisedSurvey, **_: Any) -> AmplitudeStats:
        if not survey.traces:
            raise ValueError("AmplitudeScorer: survey has no traces")

        all_values = [v for trace in survey.traces for v in trace]
        n = len(all_values)
        rms = math.sqrt(sum(v**2 for v in all_values) / n)
        peak = max(abs(v) for v in all_values)
        sorted_vals = sorted(abs(v) for v in all_values)
        p10 = sorted_vals[n // 10]
        p90 = sorted_vals[n * 9 // 10]
        dynamic_range = 20 * math.log10(peak / p10) if p10 > 0 else 0.0

        return AmplitudeStats(
            rms_amplitude=round(rms, 5),
            peak_amplitude=round(peak, 5),
            p10=round(p10, 5),
            p90=round(p90, 5),
            dynamic_range_db=round(dynamic_range, 1),
        )


class VelocityEstimator(Knot):
    """Estimates interval velocities using a simplified Dix inversion.

    A production version would perform semblance analysis on pre-stack
    gathers across offset ranges.  Here we derive velocity from the
    offset range and an assumed reflector model.
    """

    async def process(self, survey: NormalisedSurvey, **_: Any) -> VelocityModel:
        dt_s = survey.sample_rate_us * 1e-6
        total_time_s = survey.n_samples * dt_s
        target_time_ms = total_time_s * 1000 * 0.6

        v_surface = 1500.0
        v_target = 2200.0
        v_deep = 3000.0

        intervals = [
            (total_time_ms * 0.1, v_surface) for total_time_ms in [total_time_s * 1000]
        ] + [
            (total_time_s * 1000 * 0.4, v_target),
            (total_time_s * 1000 * 0.5, v_deep),
        ]

        def vrms(t_ms: float) -> float:
            t_s = t_ms / 1000
            n_layers = sum(1 for t, _ in intervals if t / 1000 <= t_s)
            if n_layers == 0:
                return v_surface
            velocities = [v for _, v in intervals[:n_layers]]
            return math.sqrt(sum(v**2 for v in velocities) / len(velocities))

        return VelocityModel(
            interval_velocities=[(round(t, 0), round(v, 0)) for t, v in intervals],
            vrms_surface=round(vrms(50), 0),
            vrms_target=round(vrms(target_time_ms), 0),
            two_way_time_ms=round(target_time_ms, 0),
        )


class HorizonPicker(Knot):
    """Identifies reflection horizons by detecting consistent amplitude peaks.

    Stacks all traces and finds peaks above a threshold; each peak
    becomes a named horizon.
    """

    _HORIZON_NAMES: ClassVar[list[str]] = [
        "seafloor",
        "top-reservoir",
        "base-reservoir",
        "basement",
    ]

    async def process(self, survey: NormalisedSurvey, **_: Any) -> list[HorizonPick]:
        if not survey.traces:
            return []

        dt_ms = survey.sample_rate_us / 1000.0
        stack = [
            sum(t[i] for t in survey.traces) / survey.n_traces for i in range(survey.n_samples)
        ]
        abs_stack = [abs(v) for v in stack]
        threshold = max(abs_stack) * 0.3

        peaks: list[tuple[int, float]] = []
        for i in range(1, len(abs_stack) - 1):
            if abs_stack[i] > abs_stack[i - 1] and abs_stack[i] > abs_stack[i + 1]:
                if abs_stack[i] > threshold:
                    peaks.append((i, abs_stack[i]))

        peaks.sort(key=lambda x: x[1], reverse=True)
        peaks = peaks[: len(self._HORIZON_NAMES)]
        peaks.sort(key=lambda x: x[0])

        horizons: list[HorizonPick] = []
        for (idx, amp), name in zip(peaks, self._HORIZON_NAMES, strict=False):
            twt_ms = idx * dt_ms
            consistency = (
                sum(1 for t in survey.traces if abs(t[idx]) > threshold * 0.5) / survey.n_traces
            )
            horizons.append(
                HorizonPick(
                    name=name,
                    two_way_time_ms=round(twt_ms, 1),
                    avg_amplitude=round(amp, 4),
                    confidence=round(consistency, 3),
                    n_traces_picked=int(consistency * survey.n_traces),
                )
            )
        return horizons


class SurveyReport(Knot):
    """Assembles all analysis outputs into a single ``SurveyResult``."""

    async def process(
        self,
        survey_name: str,
        survey: NormalisedSurvey,
        frequency: FrequencySpectrum,
        amplitude: AmplitudeStats,
        velocity: VelocityModel,
        horizons: list[HorizonPick],
        **_: Any,
    ) -> SurveyResult:
        return SurveyResult(
            survey_name=survey_name,
            n_traces=survey.n_traces,
            frequency=frequency,
            amplitude=amplitude,
            velocity=velocity,
            horizons=horizons,
        )


# ----------------------------------------------------------------- tapestry


def build_tapestry(history=None) -> Tapestry:
    with Tapestry(history=history) as t:
        survey_name = Parameter("survey_name", str, _config=KnotConfig(id="survey_name"))
        raw_traces = Parameter("traces", list, _config=KnotConfig(id="raw_traces"))

        loaded = TraceLoader(
            traces=raw_traces,
            survey_name=survey_name,
            _config=KnotConfig(id="loaded"),
        )
        normalised = TraceNormaliser(
            traces=loaded,
            _config=KnotConfig(id="normalised"),
        )
        freq = FrequencyAnalyser(
            survey=normalised,
            _config=KnotConfig(id="frequency"),
        )
        amp = AmplitudeScorer(
            survey=normalised,
            _config=KnotConfig(id="amplitude"),
        )
        vel = VelocityEstimator(
            survey=normalised,
            _config=KnotConfig(id="velocity"),
        )
        horizons = HorizonPicker(
            survey=normalised,
            _config=KnotConfig(id="horizons"),
        )
        SurveyReport(
            survey_name=survey_name,
            survey=normalised,
            frequency=freq,
            amplitude=amp,
            velocity=vel,
            horizons=horizons,
            _config=KnotConfig(id="report"),
        )
    return t


# ----------------------------------------------------------------- survey catalogue


SURVEYS = [
    "North-Sea-Block-42A",
    "Gulf-of-Mexico-GC-644",
    "Permian-Basin-3D-West",
]


# ----------------------------------------------------------------- main


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    t = build_tapestry(history=history)

    print("\n── Seismic Survey Analysis Pipeline ──\n")

    for survey_name in SURVEYS:
        traces = _synthetic_traces(survey_name)
        req = RunRequest(
            parameters={
                "survey_name": survey_name,
                "traces": traces,
            }
        )
        r = await t.run(req)
        if not r.succeeded:
            exc = r.exceptions[0]
            print(f"  FAILED ({exc.knot_id}): {exc.message[:80]}")
            continue
        result: SurveyResult = r.outputs["report"]
        print(result.summary())
        print()


if __name__ == "__main__":
    asyncio.run(main())
