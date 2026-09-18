"""``AnomalyReport`` — what the anomaly screen found in one study.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnomalyReport:
    """Anomaly screening result, including whether it needs an urgent read."""

    study_id: str
    anomalies_found: bool
    severity: str
    findings: list[str]
    requires_urgent_review: bool
