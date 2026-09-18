"""``TriageDecider`` — turns one study's findings into a triage decision.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from examples.domain_formats.medical_triage_agent.anomaly_report import AnomalyReport
from examples.domain_formats.medical_triage_agent.tissue_classification import (
    TissueClassification,
)
from examples.domain_formats.medical_triage_agent.triage_ids import TriageIds
from examples.domain_formats.medical_triage_agent.triage_outcome import TriageOutcome
from examples.domain_formats.medical_triage_agent.triage_queue import TriageQueue
from examples.domain_formats.medical_triage_agent.triage_report import _TriageReport
from examples.domain_formats.medical_triage_agent.windowing_result import WindowingResult


class TriageDecider(Knot):
    """Assembles a TriageOutcome and dispatches the next study or finalises."""

    async def process(
        self,
        queue: TriageQueue,
        findings: list[Any],
        **_: Any,
    ) -> TriageQueue:
        by_type: dict[str, Any] = {}
        for item in findings:
            by_type[type(item).__name__] = item

        windowing: WindowingResult = by_type["WindowingResult"]
        tissue: TissueClassification = by_type["TissueClassification"]
        anomalies: AnomalyReport = by_type["AnomalyReport"]

        if anomalies.requires_urgent_review:
            decision = "urgent"
            rationale = (
                f"Urgent: {', '.join(anomalies.findings)} "
                f"({anomalies.severity}) in {tissue.primary_tissue}"
            )
        elif anomalies.anomalies_found:
            decision = "review"
            rationale = f"Review requested: {', '.join(anomalies.findings)} ({anomalies.severity})"
        else:
            decision = "routine"
            rationale = (
                f"No anomalies detected in {tissue.primary_tissue} "
                f"(confidence {tissue.confidence:.0%})"
            )

        outcome = TriageOutcome(
            study_id=windowing.study_id,
            decision=decision,
            windowing=windowing,
            tissue=tissue,
            anomalies=anomalies,
            rationale=rationale,
        )
        new_queue = queue.evolve(outcomes=(*queue.outcomes, outcome))

        store = Tapestry.current_store()
        if store is None:
            return new_queue

        if not new_queue.done:
            # Imported here, not at module scope: StudyDispatcher registers this
            # decider and this decider registers the next dispatcher, so the two
            # modules refer to each other.
            from examples.domain_formats.medical_triage_agent.study_dispatcher import (
                StudyDispatcher,
            )

            store.register(
                StudyDispatcher(
                    queue=self,
                    _config=KnotConfig(id=f"dispatch_{new_queue.study_idx}", validate_io=False),
                )
            )
        else:
            store.register(
                _TriageReport(
                    queue=self,
                    _config=KnotConfig(id=TriageIds.complete, validate_io=False),
                )
            )

        return new_queue
