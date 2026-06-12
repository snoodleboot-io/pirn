"""``EnsembleBuilder`` — combine multiple :class:`ModelManifest` parents
into a meta-model reference.

The base-class implementation produces a deterministic
:class:`ModelManifest` whose ``model_id`` hashes the children's
``model_id``s plus the strategy. Concrete subclasses override
:meth:`process` to perform a real stacking / blending fit.

Algorithm:
    1. Validate that at least two model_<n> kwargs are present and resolve to ModelManifest.
    2. Validate the strategy is one of the known ensemble strategies.
    3. Derive a deterministic model_id from SHA-256(strategy + child model_ids).
    4. Return a ModelManifest with algorithm ``"ensemble:<strategy>"``.

Math:
    model_id = "ensemble:<strategy>:" + sha256(strategy || child_ids)[0:16]

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.model_manifest import ModelManifest


class EnsembleBuilder(Knot):
    """Stack / blend multiple :class:`ModelManifest`s into a meta-learner."""

    valid_strategies: ClassVar[frozenset[str]] = frozenset({"stacking", "blending", "voting"})
    _model_key_re: ClassVar[re.Pattern[str]] = re.compile(r"^model_(\d+)$")

    def __init__(
        self,
        *,
        models: Sequence[Knot],
        strategy: Knot | str = "stacking",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            _config=_config,
            strategy=strategy,
            **{f"model_{i}": m for i, m in enumerate(models)},
            **kwargs,
        )

    async def process(self, strategy: str = "stacking", **kwargs: Any) -> ModelManifest:
        """Combine resolved child ModelManifest inputs into a meta-learner ModelManifest.

        Args:
            strategy: Ensemble strategy; must be one of ``valid_strategies``.

        Returns:
            ModelManifest whose ``model_id`` is a deterministic digest of the
            child model ids and ensemble strategy.

        Raises:
            ValueError: If strategy is not valid or fewer than two models provided.
            TypeError: If any ``model_<n>`` kwarg does not resolve to a ModelManifest.
        """
        if strategy not in self.valid_strategies:
            raise ValueError(
                f"EnsembleBuilder: strategy must be one of {sorted(self.valid_strategies)}"
            )
        # Collect children in index order from numbered kwargs.
        indexed: list[tuple[int, ModelManifest]] = []
        for key, value in kwargs.items():
            match = self._model_key_re.match(key)
            if match is None:
                continue
            if not isinstance(value, ModelManifest):
                raise TypeError(f"EnsembleBuilder: {key} must resolve to a ModelManifest")
            indexed.append((int(match.group(1)), value))
        if len(indexed) < 2:
            raise ValueError("EnsembleBuilder: at least two models are required")
        children: list[ModelManifest] = [m for _, m in sorted(indexed)]
        algorithm = f"ensemble:{strategy}"
        feature_names = children[0].feature_names
        target_name = children[0].target_name
        model_id = self._derive_model_id(children, strategy)
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

    def _derive_model_id(self, children: Sequence[ModelManifest], strategy: str) -> str:
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
