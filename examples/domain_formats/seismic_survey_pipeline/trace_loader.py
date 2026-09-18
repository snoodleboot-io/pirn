"""``TraceLoader`` — validates incoming trace records before analysis.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.seismic_survey_pipeline.trace_record import TraceRecord


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
