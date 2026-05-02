"""``ShadowDeployer`` — record a shadow deployment of a new model alongside
an existing one.

Pirn does not actually serve traffic here; the knot writes a
``shadow_deployment`` event to the configured :class:`LineageStore` and
returns the deployment id so downstream knots can reference it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.lineage_store import LineageStore
from pirn.domains.ml.types.trained_model import TrainedModel


class ShadowDeployer(Knot):
    """Register a shadow deployment for a :class:`TrainedModel`."""

    def __init__(
        self,
        *,
        model: Knot,
        registry: LineageStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(registry, LineageStore):
            raise TypeError(
                "ShadowDeployer: registry must be a LineageStore"
            )
        self._registry = registry
        super().__init__(model=model, _config=_config, **kwargs)

    async def process(self, model: TrainedModel, **_: Any) -> str:
        if not isinstance(model, TrainedModel):
            raise TypeError(
                "ShadowDeployer: model must resolve to a TrainedModel"
            )
        deployed_at = datetime.now(timezone.utc)
        deployment_id = self._derive_deployment_id(model, deployed_at)
        await self._registry.log_event(
            "shadow_deployment",
            {
                "deployment_id": deployment_id,
                "model_id": model.model_id,
                "algorithm": model.algorithm,
                "deployed_at": deployed_at.isoformat(),
            },
        )
        return deployment_id

    def _derive_deployment_id(
        self, model: TrainedModel, deployed_at: datetime
    ) -> str:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "deployed_at": deployed_at.isoformat(),
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"shadow:{digest[:16]}"
