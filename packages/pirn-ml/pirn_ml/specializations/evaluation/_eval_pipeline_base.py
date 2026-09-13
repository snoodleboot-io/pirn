"""``_EvalPipelineBase`` — shared model/split wiring for the *_eval_pipeline family.

``ClassificationEvalPipeline``, ``RegressionEvalPipeline``,
``RankingEvalPipeline``, and ``TimeSeriesEvalPipeline`` each re-inject
their resolved ``model``/``split`` inputs as fresh ``Parameter`` nodes
(so they participate as upstream knots inside the inner Tapestry) and
wire a single :class:`Evaluator` scored against a domain-specific metric
set. This base centralises exactly that shared pair of steps; each
subclass keeps its own ``__init__`` (constructor signatures are
unchanged) and its own extra validation/logic:

* ``ClassificationEvalPipeline`` / ``RegressionEvalPipeline`` — a fixed
  ``_metrics: ClassVar[tuple[str, ...]]`` and nothing else.
* ``RankingEvalPipeline`` — an extra ``k`` parameter; its metric tuple is
  computed at call time (``ndcg_at_k``/``map_at_k`` embed ``k``), so it
  is not a ``ClassVar``.
* ``TimeSeriesEvalPipeline`` — a fixed ``_metrics`` ClassVar plus an
  extra ``time_column`` parameter and a decoration step that records it
  on the report's ``details`` after evaluation.

Algorithm:
    1. A subclass's ``process()`` validates its own extra inputs (if any).
    2. It calls :meth:`_wire_model_split` to re-inject ``model``/``split``
       as ``Parameter`` nodes named ``"model"``/``"split"``.
    3. It calls :meth:`_evaluate` with the resolved metric tuple to wire
       the terminal (or intermediate, for ``TimeSeriesEvalPipeline``)
       ``Evaluator`` knot, keyed ``"evaluate"``.

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


class _EvalPipelineBase(SubTapestry):
    """Shared model/split re-injection and Evaluator wiring."""

    _metrics: ClassVar[tuple[str, ...]] = ()

    @staticmethod
    def _wire_model_split(model: ModelManifest, split: SplitManifest) -> tuple[Knot, Knot]:
        model_node = Parameter(
            "model", ModelManifest, default=model, _config=KnotConfig(id="model")
        )
        split_node = Parameter(
            "split", SplitManifest, default=split, _config=KnotConfig(id="split")
        )
        return model_node, split_node

    @staticmethod
    def _evaluate(model_node: Knot, split_node: Knot, metrics: tuple[str, ...]) -> Knot:
        return Evaluator(
            model=model_node,
            split=split_node,
            metrics=metrics,
            _config=KnotConfig(id="evaluate"),
        )
