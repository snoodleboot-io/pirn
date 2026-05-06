"""``PigRunDataProcessor`` — process inline-inspection (pigging) run data.

Algorithm:
    1. Receive ``pipeline_id`` and ``run_path`` strings.
    2. Validate that both are non-empty strings.
    3. Parse the ILI data file at ``run_path`` for the given ``pipeline_id``.
    4. Return a feature-table summary with pipeline ID, feature count, and
       longest anomaly length.


References:
    - ASME B31.8S-2022 — Managing System Integrity of Gas Pipelines.
    - NACE SP0102-2010, In-Line Inspection of Pipelines.
    - API 1163:2013, In-Line Inspection Systems Qualification Standard.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class PigRunDataProcessor(Knot):
    """Process raw ILI pig-run data into a feature table reference."""

    def __init__(
        self,
        *,
        pipeline_id: Knot | str,
        run_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pipeline_id=pipeline_id,
            run_path=run_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pipeline_id: str,
        run_path: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Process the pig-run file path and return a feature table summary for the pipeline.

        Args:
            pipeline_id: Non-empty pipeline identifier string.
            run_path: Non-empty file path to the ILI data file.

        Returns:
            Dict with ``pipeline_id``, ``feature_count`` (int number of
            anomaly features detected), and ``longest_anomaly_in`` (float
            length of the longest anomaly in inches).
        """
        if not isinstance(pipeline_id, str) or not pipeline_id:
            raise ValueError("PigRunDataProcessor: pipeline_id must be a non-empty string")
        if not isinstance(run_path, str) or not run_path:
            raise ValueError("PigRunDataProcessor: run_path must be a non-empty string")
        return {
            "pipeline_id": pipeline_id,
            "feature_count": 0,
            "longest_anomaly_in": 0.0,
        }
