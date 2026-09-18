"""``TraceNormaliser`` — decodes sample bytes and normalises trace amplitudes.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

import math
import struct
from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.seismic_survey_pipeline.normalised_survey import NormalisedSurvey
from examples.domain_formats.seismic_survey_pipeline.trace_record import TraceRecord


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
