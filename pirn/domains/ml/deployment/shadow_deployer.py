"""``ShadowDeployer`` — record a shadow deployment of a new model alongside
an existing one.

Pirn does not actually serve traffic here; the knot writes a
``shadow_deployment`` event to the configured :class:`LineageStore` and
returns the deployment id so downstream knots can reference it.

Algorithm:
    1. Receive ``model`` (TrainedModel) and ``registry`` (LineageStore) via process().
    2. Validate that model is a TrainedModel.
    3. Record the current UTC timestamp as deployed_at.
    4. Derive a deterministic deployment_id from SHA-256(model_id + deployed_at).
    5. Log a ``shadow_deployment`` lineage event.
    6. Return the deployment_id string.

Math:
    deployment_id = "shadow:" + sha256(model_id || deployed_at_iso)[:16]

References:
    N/A — pirn-native implementation.
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
        registry: Knot | LineageStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(model=model, registry=registry, _config=_config, **kwargs)

    async def process(self, model: TrainedModel, registry: LineageStore, **_: Any) -> str:
        """Log a shadow deployment event to the lineage store and return the generated deployment_id.

        Args:
            model: TrainedModel reference to register as a shadow deployment.
            registry: LineageStore used to log the shadow deployment event.

        Returns:
            Deterministic deployment_id string prefixed with ``"shadow:"``.

        Raises:
            TypeError: If model does not resolve to a TrainedModel.
        """
        if not isinstance(model, TrainedModel):
            raise TypeError(
                "ShadowDeployer: model must resolve to a TrainedModel"
            )
        deployed_at = datetime.now(timezone.utc)
        deployment_id = self._derive_deployment_id(model, deployed_at)
        await registry.log_event(
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
