"""``EnsembleBuilder`` — combine multiple :class:`TrainedModel` parents
into a meta-model reference.

The base-class implementation produces a deterministic
:class:`TrainedModel` whose ``model_id`` hashes the children's
``model_id``s plus the strategy. Concrete subclasses override
:meth:`process` to perform a real stacking / blending fit.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, ClassVar, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.trained_model import TrainedModel


class EnsembleBuilder(Knot):
    """Stack / blend multiple :class:`TrainedModel`s into a meta-learner."""

    valid_strategies: ClassVar[frozenset[str]] = frozenset(
        {"stacking", "blending", "voting"}
    )

    def __init__(
        self,
        *,
        models: Sequence[Knot],
        strategy: str = "stacking",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        model_tuple = tuple(models)
        if len(model_tuple) < 2:
            raise ValueError(
                "EnsembleBuilder: at least two models are required"
            )
        for index, child in enumerate(model_tuple):
            if not isinstance(child, Knot):
                raise TypeError(
                    f"EnsembleBuilder: models[{index}] must be a Knot"
                )
        if strategy not in self.valid_strategies:
            raise ValueError(
                f"EnsembleBuilder: strategy must be one of "
                f"{sorted(self.valid_strategies)}"
            )
        # Wire each child as a numbered parent so the knot framework
        # honours the dependency edge.
        parent_kwargs = {
            f"model_{index}": child for index, child in enumerate(model_tuple)
        }
        self._strategy = strategy
        self._model_count = len(model_tuple)
        super().__init__(_config=_config, **parent_kwargs, **kwargs)

    @property
    def strategy(self) -> str:
        return self._strategy

    async def process(self, **kwargs: Any) -> TrainedModel:
        children: list[TrainedModel] = []
        for index in range(self._model_count):
            value = kwargs.get(f"model_{index}")
            if not isinstance(value, TrainedModel):
                raise TypeError(
                    f"EnsembleBuilder: model_{index} must resolve to a "
                    "TrainedModel"
                )
            children.append(value)
        algorithm = f"ensemble:{self._strategy}"
        feature_names = children[0].feature_names
        target_name = children[0].target_name
        model_id = self._derive_model_id(children)
        merged_hyperparameters = MappingProxyType(
            {
                "strategy": self._strategy,
                "child_model_ids": [child.model_id for child in children],
            }
        )
        return TrainedModel(
            model_id=model_id,
            algorithm=algorithm,
            hyperparameters=merged_hyperparameters,
            feature_names=feature_names,
            target_name=target_name,
            created_at=datetime.now(timezone.utc),
        )

    def _derive_model_id(self, children: Sequence[TrainedModel]) -> str:
        payload = json.dumps(
            {
                "strategy": self._strategy,
                "child_model_ids": [child.model_id for child in children],
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"ensemble:{self._strategy}:{digest[:16]}"
