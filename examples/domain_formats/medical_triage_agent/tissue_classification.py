"""``TissueClassification`` — the tissue type identified in one study.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TissueClassification:
    """Primary tissue call for a study, with its runner-up findings."""

    study_id: str
    primary_tissue: str
    confidence: float
    secondary_findings: list[str]
