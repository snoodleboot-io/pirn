"""``AnalysedSample`` — a sample's readings with any out-of-range biomarkers flagged.

Part of the ``examples.lab_batch`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AnalysedSample:
    sample_id: str
    patient_id: str
    measurements: dict[str, float]
    flags: list[str]  # biomarkers outside reference range
    critical: bool  # any value critically abnormal
