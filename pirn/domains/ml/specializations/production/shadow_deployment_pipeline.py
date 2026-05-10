"""``ShadowDeploymentPipeline`` — SubTapestry harness that wraps
:class:`ShadowDeployer` for both a champion and a challenger model.

For every request the harness records a divergence event between the
two models in the configured :class:`LineageStore`. The output is a
mapping carrying the champion deployment id, the challenger deployment
id, and the recorded divergence id so downstream knots can correlate
the two registrations.

Algorithm:
    1. Receive ``champion``, ``challenger``, and ``lineage`` via process().
    2. Validate all inputs.
    3. Wire two ShadowDeployer knots in an inner Tapestry.
    4. Run via _run_inner(), record divergence event, and return ids.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.deployment.shadow_deployer import ShadowDeployer
from pirn.domains.ml.lineage_store import LineageStore
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class ShadowDeploymentPipeline(SubTapestry):
    """Run champion and challenger through :class:`ShadowDeployer`."""

    def __init__(
        self,
        *,
        champion: Knot,
        challenger: Knot,
        lineage: Knot | LineageStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            champion=champion,
            challenger=challenger,
            lineage=lineage,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        champion: ModelManifest,
        challenger: ModelManifest,
        lineage: LineageStore | None = None,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Shadow-deploy both the champion and challenger, record a divergence event, and return their deployment ids and the divergence id.

        Args:
            champion: Current production ModelManifest to shadow-deploy.
            challenger: Candidate ModelManifest to shadow-deploy alongside the champion.
            lineage: LineageStore for recording the divergence event.

        Returns:
            Mapping with ``champion_deployment_id``, ``challenger_deployment_id``,
            and ``divergence_id`` (a deterministic digest of the two model ids).

        Raises:
            TypeError: If lineage is not a LineageStore.
        """
        if not isinstance(lineage, LineageStore):
            raise TypeError("ShadowDeploymentPipeline: lineage must be a LineageStore")
        with Tapestry() as inner:
            champion_node = _emit_value(value=champion, _config=KnotConfig(id="champion"))
            challenger_node = _emit_value(value=challenger, _config=KnotConfig(id="challenger"))
            ShadowDeployer(
                model=champion_node,
                registry=lineage,
                _config=KnotConfig(id="deploy-champion"),
            )
            ShadowDeployer(
                model=challenger_node,
                registry=lineage,
                _config=KnotConfig(id="deploy-challenger"),
            )
        inner_result = await self._run_inner(inner)
        champion_deployment_id: str = inner_result.outputs["deploy-champion"]
        challenger_deployment_id: str = inner_result.outputs["deploy-challenger"]
        recorded_at = datetime.now(UTC).isoformat()
        divergence_id = self._derive_divergence_id(champion, challenger, recorded_at)
        await lineage.log_event(
            "shadow_divergence",
            {
                "divergence_id": divergence_id,
                "champion_deployment_id": champion_deployment_id,
                "challenger_deployment_id": challenger_deployment_id,
                "champion_model_id": champion.model_id,
                "challenger_model_id": challenger.model_id,
                "recorded_at": recorded_at,
            },
        )
        return {
            "champion_deployment_id": champion_deployment_id,
            "challenger_deployment_id": challenger_deployment_id,
            "divergence_id": divergence_id,
        }

    def _derive_divergence_id(
        self,
        champion: ModelManifest,
        challenger: ModelManifest,
        recorded_at: str,
    ) -> str:
        payload = json.dumps(
            {
                "champion_model_id": champion.model_id,
                "challenger_model_id": challenger.model_id,
                "recorded_at": recorded_at,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"divergence:{digest[:16]}"
