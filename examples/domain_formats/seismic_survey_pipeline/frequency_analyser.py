"""``FrequencyAnalyser`` — estimates dominant frequency and SNR from the stack.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

import math
from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.seismic_survey_pipeline.frequency_spectrum import FrequencySpectrum
from examples.domain_formats.seismic_survey_pipeline.normalised_survey import NormalisedSurvey


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
