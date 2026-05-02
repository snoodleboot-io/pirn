"""``RadiomicsExtractor`` — pyradiomics-style radiomic feature extractor.

Production version uses ``pyradiomics``. This stub returns an empty
mapping ``feature_name -> value``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RadiomicsExtractor(Knot):
    """Extract radiomic features from an image and ROI mask."""

    def __init__(
        self,
        *,
        image_path: str,
        mask_path: str,
        feature_classes: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("image_path", image_path),
            ("mask_path", mask_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"RadiomicsExtractor: {label} must be a non-empty string"
                )
        if not isinstance(feature_classes, (list, tuple)):
            raise TypeError(
                "RadiomicsExtractor: feature_classes must be list/tuple"
            )
        for fc in feature_classes:
            if not isinstance(fc, str):
                raise TypeError(
                    "RadiomicsExtractor: every feature class must be a string"
                )
        self._image_path = image_path
        self._mask_path = mask_path
        self._feature_classes = tuple(feature_classes)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, float]:
        return {}
