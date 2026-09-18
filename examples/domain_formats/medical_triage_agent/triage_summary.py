"""``TriageSummary`` — the serialisable run output.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

from dataclasses import dataclass

from examples.domain_formats.medical_triage_agent.triage_outcome import TriageOutcome


@dataclass(frozen=True)
class TriageSummary:
    """Serialisable run output — strips raw pixel bytes from studies."""

    n_studies: int
    outcomes: tuple[TriageOutcome, ...]
