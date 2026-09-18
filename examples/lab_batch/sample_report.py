"""``SampleReport`` — the human-readable verdict for a single sample.

Part of the ``examples.lab_batch`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SampleReport:
    sample_id: str
    patient_id: str
    status: str  # "normal" | "flagged" | "critical"
    flags: list[str]
    narrative: str
