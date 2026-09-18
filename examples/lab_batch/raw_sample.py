"""``RawSample`` — one collected patient sample and its raw biomarker readings.

Part of the ``examples.lab_batch`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RawSample:
    sample_id: str
    patient_id: str
    collected_at: str
    measurements: dict[str, float]  # biomarker → raw value
