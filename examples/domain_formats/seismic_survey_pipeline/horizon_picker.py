"""``HorizonPicker`` — names reflection horizons from consistent stack peaks.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot

from examples.domain_formats.seismic_survey_pipeline.horizon_pick import HorizonPick
from examples.domain_formats.seismic_survey_pipeline.normalised_survey import NormalisedSurvey


class HorizonPicker(Knot):
    """Identifies reflection horizons by detecting consistent amplitude peaks.

    Stacks all traces and finds peaks above a threshold; each peak
    becomes a named horizon.
    """

    _horizon_names: ClassVar[tuple[str, ...]] = (
        "seafloor",
        "top-reservoir",
        "base-reservoir",
        "basement",
    )

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
        peaks = peaks[: len(self._horizon_names)]
        peaks.sort(key=lambda x: x[0])

        horizons: list[HorizonPick] = []
        for (idx, amp), name in zip(peaks, self._horizon_names, strict=False):
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
