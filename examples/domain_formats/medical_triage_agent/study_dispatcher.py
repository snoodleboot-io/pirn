"""``StudyDispatcher`` — pulls the next study and grows the DAG around it.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry

from examples.domain_formats.medical_triage_agent.anomaly_detector import AnomalyDetector
from examples.domain_formats.medical_triage_agent.tissue_classifier import TissueClassifier
from examples.domain_formats.medical_triage_agent.triage_decider import TriageDecider
from examples.domain_formats.medical_triage_agent.triage_queue import TriageQueue
from examples.domain_formats.medical_triage_agent.windowing_analyser import WindowingAnalyser


class StudyDispatcher(Knot):
    """Pulls the next study from the queue and registers parallel analysis knots.

    Each invocation wires up WindowingAnalyser, TissueClassifier, and
    AnomalyDetector in parallel, then an Aggregator, then a TriageDecider —
    all as live nodes in the extensible tapestry.
    """

    async def process(self, queue: TriageQueue, **_: Any) -> TriageQueue:
        study = queue.current_study
        new_queue = queue.evolve(study_idx=queue.study_idx + 1)

        store = Tapestry.current_store()
        if store is None:
            return new_queue

        prefix = f"study_{queue.study_idx}"

        wind = WindowingAnalyser(
            study=study,
            _config=KnotConfig(id=f"{prefix}__window", validate_io=False),
        )
        tissue = TissueClassifier(
            study=study,
            _config=KnotConfig(id=f"{prefix}__tissue", validate_io=False),
        )
        anomaly = AnomalyDetector(
            study=study,
            tissue=tissue,
            _config=KnotConfig(id=f"{prefix}__anomaly", validate_io=False),
        )
        store.register(wind)
        store.register(tissue)
        store.register(anomaly)

        agg = Aggregator(
            combine=lambda **kw: list(kw.values()),
            windowing=wind,
            tissue=tissue,
            anomalies=anomaly,
            _config=KnotConfig(id=f"{prefix}__agg", validate_io=False),
        )
        store.register(agg)

        decider = TriageDecider(
            queue=self,
            findings=agg,
            _config=KnotConfig(id=f"{prefix}__decide", validate_io=False),
        )
        store.register(decider)

        return new_queue
