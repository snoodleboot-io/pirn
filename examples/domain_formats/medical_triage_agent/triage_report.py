"""``_TriageReport`` — the terminal knot of the triage run.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.medical_triage_agent.triage_queue import TriageQueue
from examples.domain_formats.medical_triage_agent.triage_summary import TriageSummary


class _TriageReport(Knot):
    """Terminal knot — surfaces outcomes without raw pixel bytes."""

    async def process(self, queue: TriageQueue, **_: Any) -> TriageSummary:
        return TriageSummary(
            n_studies=len(queue.studies),
            outcomes=queue.outcomes,
        )
