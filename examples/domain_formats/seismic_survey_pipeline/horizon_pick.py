"""``HorizonPick`` — one named reflection horizon picked from the stack.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HorizonPick:
    name: str
    two_way_time_ms: float
    avg_amplitude: float
    confidence: float
    n_traces_picked: int
