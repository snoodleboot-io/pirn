"""``RegionOfInterestExtractor`` — extract per-ROI statistics.

Production version applies an atlas-aligned label volume and computes
mean/std per label. This stub returns an empty mapping
``roi_label -> mean_intensity``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RegionOfInterestExtractor(Knot):
    """Extract per-ROI statistics from an aligned MRI."""

    def __init__(
        self,
        *,
        nifti_path: str,
        atlas_label_path: str,
        roi_labels: Sequence[int],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("nifti_path", nifti_path),
            ("atlas_label_path", atlas_label_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"RegionOfInterestExtractor: {label} must be a non-empty string"
                )
        if not isinstance(roi_labels, (list, tuple)):
            raise TypeError(
                "RegionOfInterestExtractor: roi_labels must be list/tuple"
            )
        for lbl in roi_labels:
            if not isinstance(lbl, int):
                raise TypeError(
                    "RegionOfInterestExtractor: every roi label must be int"
                )
        self._nifti_path = nifti_path
        self._atlas_label_path = atlas_label_path
        self._roi_labels = tuple(roi_labels)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[int, float]:
        """Extract mean intensity per ROI label from the atlas-aligned NIfTI and return a label-to-intensity mapping.

        Returns:
            Mapping of integer ROI label to mean intensity value.
        """
        return {lbl: 0.0 for lbl in self._roi_labels}
