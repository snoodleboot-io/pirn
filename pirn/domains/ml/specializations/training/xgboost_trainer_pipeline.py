"""``XGBoostTrainerPipeline`` — train, evaluate, serialise (xgboost-json)
and register an XGBoost model.

Composition mirrors :class:`SklearnTrainerPipeline` but with XGBoost
defaults:

* ``algorithm`` defaults to ``"xgboost"``.
* :class:`ModelSerializer` is configured with ``format="xgboost-json"``.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.ml.deployment.model_registrar import ModelRegistrar
from pirn.domains.ml.deployment.model_serializer import ModelSerializer
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.lineage_store import LineageStore
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class XGBoostTrainerPipeline(SubTapestry):
    """Train, evaluate, serialise (xgboost-json) and register an XGBoost model."""

    def __init__(
        self,
        *,
        split: Knot,
        lineage: LineageStore,
        store: ObjectStore,
        metrics: Sequence[str],
        algorithm: str = "xgboost",
        hyperparameters: Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("XGBoostTrainerPipeline: split must be a Knot")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "XGBoostTrainerPipeline: algorithm must be a non-empty string"
            )
        if not isinstance(lineage, LineageStore):
            raise TypeError(
                "XGBoostTrainerPipeline: lineage must be a LineageStore"
            )
        if not isinstance(store, ObjectStore):
            raise TypeError(
                "XGBoostTrainerPipeline: store must be an ObjectStore"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError(
                "XGBoostTrainerPipeline: metrics must be non-empty"
            )
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "XGBoostTrainerPipeline: every metric name must be a "
                    "non-empty string"
                )
        if hyperparameters is not None and not isinstance(
            hyperparameters, Mapping
        ):
            raise TypeError(
                "XGBoostTrainerPipeline: hyperparameters must be a Mapping"
            )
        self._algorithm = algorithm
        self._lineage = lineage
        self._store = store
        self._metrics = metric_tuple
        self._hyperparameters = (
            dict(hyperparameters) if hyperparameters is not None else {}
        )
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def serializer_format(self) -> str:
        return "xgboost-json"

    async def process(
        self, split: DataSplit, **_: Any
    ) -> dict[str, Any]:
        """Train the XGBoost model, evaluate it, serialise as xgboost-json, register it, and return a summary dict.

        Args:
            split: DataSplit used for training and evaluation.

        Returns:
            Dict with ``model_id`` (str), ``eval_report`` (:class:`EvalReport`),
            and ``serialized_size`` (int byte count of the xgboost-json artifact).

        Raises:
            TypeError: If the evaluator, serializer, or registrar output has an
                unexpected type.
        """
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            model = Trainer(
                split=split_node,
                algorithm=self._algorithm,
                hyperparameters=self._hyperparameters,
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=model,
                split=split_node,
                metrics=self._metrics,
                _config=KnotConfig(id="evaluate"),
            )
            serialized = ModelSerializer(
                model=model,
                format=self.serializer_format,
                _config=KnotConfig(id="serialize"),
            )
            ModelRegistrar(
                serialized=serialized,
                model=model,
                lineage=self._lineage,
                store=self._store,
                _config=KnotConfig(id="register"),
            )
        result = await self._run_inner(inner)
        report = result.outputs["evaluate"]
        serialized_bytes = result.outputs["serialize"]
        model_id = result.outputs["register"]
        if not isinstance(report, EvalReport):
            raise TypeError(
                "XGBoostTrainerPipeline: evaluator did not return an "
                "EvalReport"
            )
        if not isinstance(serialized_bytes, (bytes, bytearray)):
            raise TypeError(
                "XGBoostTrainerPipeline: serializer did not return bytes"
            )
        if not isinstance(model_id, str):
            raise TypeError(
                "XGBoostTrainerPipeline: registrar did not return a string id"
            )
        return {
            "model_id": model_id,
            "eval_report": report,
            "serialized_size": len(bytes(serialized_bytes)),
        }
