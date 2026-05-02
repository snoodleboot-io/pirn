"""``CorticalThicknessEstimator`` — estimate per-region cortical thickness.

Production version uses FreeSurfer or DiReCT (ANTs). This stub returns
an empty mapping ``region -> thickness_mm``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class CorticalThicknessEstimator(Knot):
    """Estimate cortical thickness per region from a T1w MRI."""

    def __init__(
        self,
        *,
        t1_nifti_path: str,
        regions: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(t1_nifti_path, str) or not t1_nifti_path:
            raise ValueError(
                "CorticalThicknessEstimator: t1_nifti_path must be non-empty"
            )
        if not isinstance(regions, (list, tuple)):
            raise TypeError(
                "CorticalThicknessEstimator: regions must be list/tuple"
            )
        for region in regions:
            if not isinstance(region, str):
                raise TypeError(
                    "CorticalThicknessEstimator: every region must be a string"
                )
        self._t1_nifti_path = t1_nifti_path
        self._regions = tuple(regions)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, float]:
        return {region: 0.0 for region in self._regions}
