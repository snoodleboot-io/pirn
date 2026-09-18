"""``WindowingResult`` — the window level/width chosen for one study.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowingResult:
    """Display windowing parameters derived from a study's pixel statistics."""

    study_id: str
    window_level: float
    window_width: float
    clipped_fraction: float
