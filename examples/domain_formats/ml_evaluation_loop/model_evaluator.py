"""``ModelEvaluator`` — loads the current model and grows the DAG around it.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry

from examples.domain_formats.ml_evaluation_loop.batch_inference import BatchInference
from examples.domain_formats.ml_evaluation_loop.evaluation_queue import EvaluationQueue
from examples.domain_formats.ml_evaluation_loop.layer_profiler import LayerProfiler
from examples.domain_formats.ml_evaluation_loop.metrics_aggregator import MetricsAggregator
from examples.domain_formats.ml_evaluation_loop.promotion_decider import PromotionDecider


class ModelEvaluator(Knot):
    """Dynamic dispatcher — loads the current model and registers evaluation sub-graph."""

    async def process(self, queue: EvaluationQueue, **_: Any) -> EvaluationQueue:
        store = Tapestry.current_store()
        if store is None:
            return queue

        model = queue.current_model
        prefix = self.knot_id

        batch_knot = BatchInference(
            artifact=model,
            _config=KnotConfig(id=f"{prefix}__batch", validate_io=False),
        )
        store.register(batch_knot)

        profiler_knot = LayerProfiler(
            artifact=model,
            _config=KnotConfig(id=f"{prefix}__profile", validate_io=False),
        )
        store.register(profiler_knot)

        agg = Aggregator(
            combine=lambda **kw: list(kw.values()),
            batches=batch_knot,
            profile=profiler_knot,
            _config=KnotConfig(id=f"{prefix}__agg", validate_io=False),
        )
        store.register(agg)

        metrics_knot = MetricsAggregator(
            combined=agg,
            _config=KnotConfig(id=f"{prefix}__metrics", validate_io=False),
        )
        store.register(metrics_knot)

        decider = PromotionDecider(
            metrics=metrics_knot,
            queue=self,
            _config=KnotConfig(id=f"{prefix}__decide", validate_io=False),
        )
        store.register(decider)

        return queue
