"""``AmplitudeScorer`` — computes RMS, peak, percentiles and dynamic range.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

import math
from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.seismic_survey_pipeline.amplitude_stats import AmplitudeStats
from examples.domain_formats.seismic_survey_pipeline.normalised_survey import NormalisedSurvey


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
