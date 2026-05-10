"""``NeuralNetTrainerPipeline`` — train, evaluate, serialise and register
a neural-network model.

Composition mirrors :class:`SklearnTrainerPipeline` but is shaped for
NN-style hyperparameters (``epochs``, ``batch_size``, ``learning_rate``,
``optimizer``) and supports two artifact formats: ``"onnx"`` (default,
portable export) or ``"pytorch"`` (native checkpoint).

Algorithm:
    1. Receive ``split``, ``lineage``, ``store``, ``metrics``,
       ``algorithm``, ``hyperparameters``, and ``format`` via process().
    2. Validate all inputs.
    3. Wire Trainer → Evaluator → ModelSerializer → ModelRegistrar in an
       inner Tapestry.
    4. Run via _run_inner() and return model_id, eval_report, serialized_size.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.ml.deployment.model_registrar import ModelRegistrar
from pirn.domains.ml.deployment.model_serializer import ModelSerializer
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.lineage_store import LineageStore
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.split_manifest import SplitManifest
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
        lineage: Knot | LineageStore,
        store: Knot | ObjectStore,
        metrics: Knot | Sequence[str],
        algorithm: Knot | str = "pytorch",
        hyperparameters: Knot | Mapping[str, Any] | None = None,
        format: Knot | str = "onnx",
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
            format=format,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        lineage: LineageStore | None = None,
        store: ObjectStore | None = None,
        metrics: Sequence[str] = (),
        algorithm: str = "pytorch",
        hyperparameters: Mapping[str, Any] | None = None,
        format: str = "onnx",
        **_: Any,
    ) -> dict[str, Any]:
        """Train the neural-net model, evaluate it, serialise in the configured format, register it, and return a summary dict.

        Args:
            split: SplitManifest used for training and evaluation.
            lineage: LineageStore for model registration.
            store: ObjectStore for artifact storage.
            metrics: Non-empty sequence of metric names.
            algorithm: Non-empty algorithm identifier; defaults to "pytorch".
            hyperparameters: Optional mapping of additional hyperparameters.
            format: Serialization format; must be one of {"onnx", "pytorch"}.

        Returns:
            Dict with ``model_id`` (str), ``eval_report`` (:class:`EvalMetadata`),
            and ``serialized_size`` (int byte count of the serialized artifact).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If the evaluator, serializer, or registrar output has an unexpected type.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("NeuralNetTrainerPipeline: algorithm must be a non-empty string")
        if not isinstance(lineage, LineageStore):
            raise TypeError("NeuralNetTrainerPipeline: lineage must be a LineageStore")
        if not isinstance(store, ObjectStore):
            raise TypeError("NeuralNetTrainerPipeline: store must be an ObjectStore")
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("NeuralNetTrainerPipeline: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "NeuralNetTrainerPipeline: every metric name must be a non-empty string"
                )
        if hyperparameters is not None and not isinstance(hyperparameters, Mapping):
            raise TypeError("NeuralNetTrainerPipeline: hyperparameters must be a Mapping")
        if format not in self.valid_formats:
            raise ValueError(
                f"NeuralNetTrainerPipeline: format must be one of {sorted(self.valid_formats)}"
            )
        hp = dict(hyperparameters) if hyperparameters is not None else {}
        with Tapestry() as inner:
            split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
            model = Trainer(
                split=split_node,
                algorithm=algorithm,
                hyperparameters=hp,
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=model,
                split=split_node,
                metrics=metric_tuple,
                _config=KnotConfig(id="evaluate"),
            )
            serialized = ModelSerializer(
                model=model,
                format=format,
                _config=KnotConfig(id="serialize"),
            )
            ModelRegistrar(
                serialized=serialized,
                model=model,
                lineage=lineage,
                store=store,
                _config=KnotConfig(id="register"),
            )
        result = await self._run_inner(inner)
        report = result.outputs["evaluate"]
        serialized_bytes = result.outputs["serialize"]
        model_id = result.outputs["register"]
        if not isinstance(report, EvalReportPayload):
            raise TypeError(
                "NeuralNetTrainerPipeline: evaluator did not return an EvalReportPayload"
            )
        if not isinstance(serialized_bytes, (bytes, bytearray)):
            raise TypeError("NeuralNetTrainerPipeline: serializer did not return bytes")
        if not isinstance(model_id, str):
            raise TypeError("NeuralNetTrainerPipeline: registrar did not return a string id")
        return {
            "model_id": model_id,
            "eval_report": report,
            "serialized_size": len(bytes(serialized_bytes)),
        }
