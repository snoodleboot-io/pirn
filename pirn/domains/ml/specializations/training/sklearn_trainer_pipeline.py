"""``SklearnTrainerPipeline`` — train an sklearn-flavoured model, score
it, serialise the artifact, and register it with a
:class:`LineageStore` + :class:`ObjectStore`.

Composition (Block 5: ``training`` → ``evaluation`` → ``deployment``):

1. :class:`Trainer` fits the configured algorithm.
2. :class:`Evaluator` scores the model on ``split.test``.
3. :class:`ModelSerializer` (``format="joblib"``) materialises the
   artifact bytes.
4. :class:`ModelRegistrar` writes the bytes to the object store and
   logs the registration event with the lineage store.

The output is a primitive ``Mapping`` with ``model_id``, ``eval_report``
and ``serialized_size``.

Algorithm:
    1. Receive ``split``, ``algorithm``, ``lineage``, ``store``,
       ``metrics``, and ``hyperparameters`` via process().
    2. Validate all inputs.
    3. Wire Trainer → Evaluator → ModelSerializer → ModelRegistrar in an
       inner Tapestry.
    4. Run via _run_inner() and return model_id, eval_report, serialized_size.


References:
    N/A — pirn-native implementation.
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


class SklearnTrainerPipeline(SubTapestry):
    """Train, evaluate, serialise (joblib) and register an sklearn model."""

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: Knot | str,
        lineage: Knot | LineageStore,
        store: Knot | ObjectStore,
        metrics: Knot | Sequence[str],
        hyperparameters: Knot | Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            algorithm=algorithm,
            lineage=lineage,
            store=store,
            metrics=metrics,
            hyperparameters=hyperparameters,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: DataSplit,
        algorithm: str = "",
        lineage: LineageStore | None = None,
        store: ObjectStore | None = None,
        metrics: Sequence[str] = (),
        hyperparameters: Mapping[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Train the sklearn model, evaluate it, serialise with joblib, register it, and return a summary dict.

        Args:
            split: DataSplit used for training and evaluation.
            algorithm: Non-empty algorithm identifier.
            lineage: LineageStore for model registration.
            store: ObjectStore for artifact storage.
            metrics: Non-empty sequence of metric names.
            hyperparameters: Optional mapping of additional hyperparameters.

        Returns:
            Dict with ``model_id`` (str), ``eval_report`` (:class:`EvalReport`),
            and ``serialized_size`` (int byte count of the joblib artifact).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If the evaluator, serializer, or registrar output has an unexpected type.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("SklearnTrainerPipeline: algorithm must be a non-empty string")
        if not isinstance(lineage, LineageStore):
            raise TypeError("SklearnTrainerPipeline: lineage must be a LineageStore")
        if not isinstance(store, ObjectStore):
            raise TypeError("SklearnTrainerPipeline: store must be an ObjectStore")
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("SklearnTrainerPipeline: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "SklearnTrainerPipeline: every metric name must be a non-empty string"
                )
        if hyperparameters is not None and not isinstance(hyperparameters, Mapping):
            raise TypeError("SklearnTrainerPipeline: hyperparameters must be a Mapping")
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
                format="joblib",
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
        if not isinstance(report, EvalReport):
            raise TypeError(
                "SklearnTrainerPipeline: evaluator did not return an EvalReport"
            )
        if not isinstance(serialized_bytes, (bytes, bytearray)):
            raise TypeError(
                "SklearnTrainerPipeline: serializer did not return bytes"
            )
        if not isinstance(model_id, str):
            raise TypeError(
                "SklearnTrainerPipeline: registrar did not return a string id"
            )
        return {
            "model_id": model_id,
            "eval_report": report,
            "serialized_size": len(bytes(serialized_bytes)),
        }
