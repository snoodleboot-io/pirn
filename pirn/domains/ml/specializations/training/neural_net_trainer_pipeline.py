"""``NeuralNetTrainerPipeline`` — train, evaluate, serialise and register
a neural-network model.

Composition mirrors :class:`SklearnTrainerPipeline` but is shaped for
NN-style hyperparameters (``epochs``, ``batch_size``, ``learning_rate``,
``optimizer``) and supports two artifact formats: ``"onnx"`` (default,
portable export) or ``"pytorch"`` (native checkpoint).
"""

from __future__ import annotations

from typing import Any, ClassVar, Mapping, Sequence

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


class NeuralNetTrainerPipeline(SubTapestry):
    """Train, evaluate, serialise and register a neural-net model."""

    valid_formats: ClassVar[frozenset[str]] = frozenset({"onnx", "pytorch"})

    def __init__(
        self,
        *,
        split: Knot,
        lineage: LineageStore,
        store: ObjectStore,
        metrics: Sequence[str],
        algorithm: str = "pytorch",
        hyperparameters: Mapping[str, Any] | None = None,
        format: str = "onnx",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError(
                "NeuralNetTrainerPipeline: split must be a Knot"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "NeuralNetTrainerPipeline: algorithm must be a non-empty "
                "string"
            )
        if not isinstance(lineage, LineageStore):
            raise TypeError(
                "NeuralNetTrainerPipeline: lineage must be a LineageStore"
            )
        if not isinstance(store, ObjectStore):
            raise TypeError(
                "NeuralNetTrainerPipeline: store must be an ObjectStore"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError(
                "NeuralNetTrainerPipeline: metrics must be non-empty"
            )
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "NeuralNetTrainerPipeline: every metric name must be a "
                    "non-empty string"
                )
        if hyperparameters is not None and not isinstance(
            hyperparameters, Mapping
        ):
            raise TypeError(
                "NeuralNetTrainerPipeline: hyperparameters must be a Mapping"
            )
        if format not in self.valid_formats:
            raise ValueError(
                f"NeuralNetTrainerPipeline: format must be one of "
                f"{sorted(self.valid_formats)}"
            )
        self._algorithm = algorithm
        self._lineage = lineage
        self._store = store
        self._metrics = metric_tuple
        self._hyperparameters = (
            dict(hyperparameters) if hyperparameters is not None else {}
        )
        self._format = format
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def serializer_format(self) -> str:
        return self._format

    async def process(
        self, split: DataSplit, **_: Any
    ) -> dict[str, Any]:
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
                format=self._format,
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
                "NeuralNetTrainerPipeline: evaluator did not return an "
                "EvalReport"
            )
        if not isinstance(serialized_bytes, (bytes, bytearray)):
            raise TypeError(
                "NeuralNetTrainerPipeline: serializer did not return bytes"
            )
        if not isinstance(model_id, str):
            raise TypeError(
                "NeuralNetTrainerPipeline: registrar did not return a string id"
            )
        return {
            "model_id": model_id,
            "eval_report": report,
            "serialized_size": len(bytes(serialized_bytes)),
        }
