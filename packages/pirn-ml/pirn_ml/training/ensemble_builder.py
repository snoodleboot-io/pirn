"""``EnsembleBuilder`` — combine multiple :class:`ModelManifest` parents
into a meta-model reference.

The base-class implementation produces a deterministic
:class:`ModelManifest` whose ``model_id`` hashes the children's
``model_id``s plus the strategy. Concrete subclasses override
:meth:`process` to perform a real stacking / blending fit.

Algorithm:
    1. The constructor wires the caller's model knots behind a single
       internal :class:`~pirn.nodes.aggregator.Aggregator` that combines
       them, in the caller's order, into one ``tuple[ModelManifest, ...]``
       parent named ``models``.
    2. ``process()`` receives that resolved tuple directly (Rule 2) and
       validates it has at least two elements, all ``ModelManifest``.
    3. Validate the strategy is one of the known ensemble strategies.
    4. Derive a deterministic model_id from SHA-256(strategy + child model_ids).
    5. Return a ModelManifest with algorithm ``"ensemble:<strategy>"``.

Math:
    model_id = "ensemble:<strategy>:" + sha256(strategy || child_ids)[0:16]

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.aggregator import Aggregator

from pirn_ml.types.model_manifest import ModelManifest


class EnsembleBuilder(Knot):
    """Stack / blend multiple :class:`ModelManifest`s into a meta-learner."""

    valid_strategies: ClassVar[frozenset[str]] = frozenset({"stacking", "blending", "voting"})

    def __init__(
        self,
        *,
        models: Sequence[Knot],
        strategy: Knot | str = "stacking",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        numbered = {f"model_{i}": model for i, model in enumerate(models)}
        models_node = Aggregator(
            combine=EnsembleBuilder._order_models,
            _config=KnotConfig(id=f"{_config.id}:models"),
            **numbered,
        )
        super().__init__(
            models=models_node,
            strategy=strategy,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        models: tuple[ModelManifest, ...] = (),
        strategy: str = "stacking",
        **_: Any,
    ) -> ModelManifest:
        """Combine resolved child ModelManifest inputs into a meta-learner ModelManifest.

        Args:
            models: Child ModelManifests in constructor order.
            strategy: Ensemble strategy; must be one of ``valid_strategies``.

        Returns:
            ModelManifest whose ``model_id`` is a deterministic digest of the
            child model ids and ensemble strategy.

        Raises:
            ValueError: If strategy is not valid or fewer than two models provided.
            TypeError: If any element of ``models`` is not a ModelManifest.
        """
        if strategy not in self.valid_strategies:
            raise ValueError(
                f"EnsembleBuilder: strategy must be one of {sorted(self.valid_strategies)}"
            )
        for child in models:
            if not isinstance(child, ModelManifest):
                raise TypeError("EnsembleBuilder: every model must resolve to a ModelManifest")
        if len(models) < 2:
            raise ValueError("EnsembleBuilder: at least two models are required")
        children = list(models)
        algorithm = f"ensemble:{strategy}"
        feature_names = children[0].feature_names
        target_name = children[0].target_name
        model_id = EnsembleBuilder._derive_model_id(children, strategy)
        merged_hyperparameters = MappingProxyType(
            {
                "strategy": strategy,
                "child_model_ids": [child.model_id for child in children],
            }
        )
        return ModelManifest(
            model_id=model_id,
            algorithm=algorithm,
            hyperparameters=merged_hyperparameters,
            feature_names=feature_names,
            target_name=target_name,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _order_models(**kwargs: Any) -> tuple[Any, ...]:
        """Order ``model_<n>`` kwargs by their numeric index (Aggregator combine callback)."""
        indexed = [(int(key.split("_", 1)[1]), value) for key, value in kwargs.items()]
        return tuple(value for _, value in sorted(indexed))

    @staticmethod
    def _derive_model_id(children: Sequence[ModelManifest], strategy: str) -> str:
        payload = json.dumps(
            {
                "strategy": strategy,
                "child_model_ids": [child.model_id for child in children],
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"ensemble:{strategy}:{digest[:16]}"
