"""``PigRunDataProcessor`` — process inline-inspection (pigging) run data."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class PigRunDataProcessor(Knot):
    """Process raw ILI pig-run data into a feature table reference."""

    def __init__(
        self,
        *,
        pipeline_id: str,
        run_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pipeline_id, str) or not pipeline_id:
            raise ValueError(
                "PigRunDataProcessor: pipeline_id must be a non-empty string"
            )
        if not isinstance(run_path, str) or not run_path:
            raise ValueError(
                "PigRunDataProcessor: run_path must be a non-empty string"
            )
        self._pipeline_id = pipeline_id
        self._run_path = run_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "pipeline_id": self._pipeline_id,
            "feature_count": 0,
            "longest_anomaly_in": 0.0,
        }
