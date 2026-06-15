"""``XGBoostTrainerPipeline`` — train, evaluate, serialise (xgboost-json)
and register an XGBoost model.

Composition mirrors :class:`SklearnTrainerPipeline` but with XGBoost
defaults:

* ``algorithm`` defaults to ``"xgboost"``.
* :class:`ModelSerializer` is configured with ``format="xgboost-json"``.

Algorithm:
    1. Receive ``split``, ``lineage``, ``store``, ``metrics``,
       ``algorithm``, and ``hyperparameters`` via process().
    2. Validate all inputs.
    3. Wire Trainer → Evaluator → ModelSerializer → ModelRegistrar in an
       inner Tapestry.
    4. Run via _run_inner() and return model_id, eval_report, serialized_size.

Math:
    XGBoost additive model: F_T(x) = sum_{t=1}^{T} f_t(x)
    Regularised objective:  L = sum_i l(y_i, F_T(x_i)) + sum_t Omega(f_t)
    where Omega(f) = gamma*|leaves| + 0.5*lambda*||w||^2

    serialized_size = len(model.save_raw())  [bytes, xgboost-json format]

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.connectors.object_store import ObjectStore
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.deployment.model_registrar import ModelRegistrar
from pirn_ml.deployment.model_serializer import ModelSerializer
from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.lineage_store import LineageStore
from pirn_ml.training.trainer import Trainer
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def _emit_value(value: Any) -> Any:
    return value


@knot
async def _combine_xgboost_pipeline_result(
    model_id: str,
    eval_report: EvalReportPayload,
    serialized: Any,
) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "eval_report": eval_report,
        "serialized_size": len(bytes(serialized)),
    }


class XGBoostTrainerPipeline(SubTapestry):
    """Train, evaluate, serialise (xgboost-json) and register an XGBoost model."""

    def __init__(
        self,
        *,
        split: Knot,
        lineage: Knot | LineageStore,
        store: Knot | ObjectStore,
        metrics: Knot | Sequence[str],
        algorithm: Knot | str = "xgboost",
        hyperparameters: Knot | Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            lineage=lineage,
            store=store,
            metrics=metrics,
            algorithm=algorithm,
            hyperparameters=hyperparameters,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        lineage: LineageStore | None = None,
        store: ObjectStore | None = None,
        metrics: Sequence[str] = (),
        algorithm: str = "xgboost",
        hyperparameters: Mapping[str, Any] | None = None,
        **_: Any,
    ) -> Any:
        """Train the XGBoost model, evaluate it, serialise as xgboost-json, register it, and return a summary dict.

        Args:
            split: SplitManifest used for training and evaluation.
            lineage: LineageStore for model registration.
            store: ObjectStore for artifact storage.
            metrics: Non-empty sequence of metric names.
            algorithm: Non-empty algorithm identifier; defaults to "xgboost".
            hyperparameters: Optional mapping of additional hyperparameters.

        Returns:
            Dict with ``model_id`` (str), ``eval_report`` (:class:`EvalMetadata`),
            and ``serialized_size`` (int byte count of the xgboost-json artifact).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If the evaluator, serializer, or registrar output has an unexpected type.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("XGBoostTrainerPipeline: algorithm must be a non-empty string")
        if not isinstance(lineage, LineageStore):
            raise TypeError("XGBoostTrainerPipeline: lineage must be a LineageStore")
        if not isinstance(store, ObjectStore):
            raise TypeError("XGBoostTrainerPipeline: store must be an ObjectStore")
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("XGBoostTrainerPipeline: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "XGBoostTrainerPipeline: every metric name must be a non-empty string"
                )
        if hyperparameters is not None and not isinstance(hyperparameters, Mapping):
            raise TypeError("XGBoostTrainerPipeline: hyperparameters must be a Mapping")
        hp = dict(hyperparameters) if hyperparameters is not None else {}
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        model = Trainer(
            split=split_node,
            algorithm=algorithm,
            hyperparameters=hp,
            _config=KnotConfig(id="train"),
        )
        evaluated = Evaluator(
            model=model,
            split=split_node,
            metrics=metric_tuple,
            _config=KnotConfig(id="evaluate"),
        )
        serialized = ModelSerializer(
            model=model,
            format="xgboost-json",
            _config=KnotConfig(id="serialize"),
        )
        registered = ModelRegistrar(
            serialized=serialized,
            model=model,
            lineage=lineage,
            store=store,
            _config=KnotConfig(id="register"),
        )
        return _combine_xgboost_pipeline_result(
            model_id=registered,
            eval_report=evaluated,
            serialized=serialized,
            _config=KnotConfig(id="combine"),
        )
