"""``TriageOutcome`` — the triage verdict for one study and the evidence behind it.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

from dataclasses import dataclass

from examples.domain_formats.medical_triage_agent.anomaly_report import AnomalyReport
from examples.domain_formats.medical_triage_agent.tissue_classification import (
    TissueClassification,
)
from examples.domain_formats.medical_triage_agent.windowing_result import WindowingResult


@dataclass(frozen=True)
class TriageOutcome:
    """One study's decision (``routine`` | ``review`` | ``urgent``) and its inputs."""

    study_id: str
    decision: str
    windowing: WindowingResult
    tissue: TissueClassification
    anomalies: AnomalyReport
    rationale: str
