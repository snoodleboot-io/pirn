"""``VolumetricAnalyzer`` — per-region volume estimates.

Production version uses FreeSurfer aseg/aparc volumes or FSL FAST.
This stub returns an empty mapping ``region -> volume_mm3``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VolumetricAnalyzer(Knot):
    """Compute per-region volumes from a labelled MRI."""

    def __init__(
        self,
        *,
        labelled_nifti_path: str,
        regions: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(labelled_nifti_path, str) or not labelled_nifti_path:
            raise ValueError(
                "VolumetricAnalyzer: labelled_nifti_path must be non-empty"
            )
        if not isinstance(regions, (list, tuple)):
            raise TypeError(
                "VolumetricAnalyzer: regions must be a list or tuple"
            )
        for region in regions:
            if not isinstance(region, str):
                raise TypeError(
                    "VolumetricAnalyzer: every region must be a string"
                )
        self._labelled_nifti_path = labelled_nifti_path
        self._regions = tuple(regions)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, float]:
        """Compute per-region volumes from the labelled NIfTI and return a region-to-volume-mm3 mapping.

        Returns:
            Mapping of region name to volume in cubic millimetres.
        """
        return {region: 0.0 for region in self._regions}
