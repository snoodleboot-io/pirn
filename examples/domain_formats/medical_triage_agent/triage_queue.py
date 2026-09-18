"""``TriageQueue`` — the immutable loop state carried through the dynamic DAG.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from examples.domain_formats.medical_triage_agent.study import Study
from examples.domain_formats.medical_triage_agent.triage_outcome import TriageOutcome


@dataclass(frozen=True)
class TriageQueue:
    """Studies still to process, plus the outcomes decided so far."""

    studies: tuple[Study, ...]
    study_idx: int = 0
    outcomes: tuple[TriageOutcome, ...] = ()

    @property
    def current_study(self) -> Study:
        return self.studies[self.study_idx]

    @property
    def done(self) -> bool:
        return self.study_idx >= len(self.studies)

    def evolve(self, **changes: Any) -> TriageQueue:
        """Return a copy of this queue with ``changes`` applied."""
        return replace(self, **changes)
