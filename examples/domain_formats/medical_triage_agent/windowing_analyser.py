"""``WindowingAnalyser`` — picks display windowing parameters for a study.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot

from examples.domain_formats.medical_triage_agent.seeded_rng import SeededRng
from examples.domain_formats.medical_triage_agent.study import Study
from examples.domain_formats.medical_triage_agent.windowing_result import WindowingResult


class WindowingAnalyser(Knot):
    """Determines optimal windowing parameters from pixel statistics.

    In a real pipeline this would use the float32 pixel array from
    DicomRecord.pixel_data, compute histogram percentiles, and choose a
    window level and width appropriate for the modality.
    """

    _modality_windows: ClassVar[dict[str, tuple[float, float]]] = {
        "CT": (40.0, 400.0),
        "MRI": (128.0, 256.0),
        "XR": (2048.0, 4096.0),
        "US": (128.0, 128.0),
    }

    async def process(self, study: Study, **_: Any) -> WindowingResult:
        rng = SeededRng.for_study(study.study_id, "window")
        level, width = self._modality_windows.get(study.modality, (128.0, 256.0))
        level += rng.uniform(-level * 0.1, level * 0.1)
        width += rng.uniform(-width * 0.05, width * 0.05)
        clipped = rng.uniform(0.001, 0.04)
        return WindowingResult(
            study_id=study.study_id,
            window_level=round(level, 1),
            window_width=round(width, 1),
            clipped_fraction=round(clipped, 4),
        )
