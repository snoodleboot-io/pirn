"""``RadiomicsExtractor`` — pyradiomics-style radiomic feature extractor.

Production version uses ``pyradiomics``. This stub returns an empty
mapping ``feature_name -> value``.

Algorithm:
    1. Receive image_path, mask_path strings, and feature_classes sequence.
    2. Validate paths are non-empty and feature_classes is list/tuple of strings.
    3. Load image and ROI mask from the given paths.
    4. Compute first-order, texture, and shape features per class.
    5. Return a mapping of feature name to numeric value.

Math:
    Grey-level co-occurrence matrix (GLCM) contrast:

    $$\\text{Contrast} = \\sum_{i,j} (i - j)^2 P(i,j)$$

References:
    - van Griethuysen et al. (2017) Computational Radiomics System to Decode the Radiographic Phenotype.
    - pyradiomics: https://pyradiomics.readthedocs.io/
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
        image_path: Knot | str,
        mask_path: Knot | str,
        feature_classes: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            image_path=image_path,
            mask_path=mask_path,
            feature_classes=feature_classes,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        image_path: str,
        mask_path: str,
        feature_classes: Sequence[str],
        **_: Any,
    ) -> Mapping[str, float]:
        """Extract radiomic features from the image-mask pair for the configured feature classes and return the mapping.

        Args:
            image_path: Non-empty path to the image NIfTI file.
            mask_path: Non-empty path to the ROI mask NIfTI file.
            feature_classes: List or tuple of feature class name strings.

        Returns:
            Mapping of feature name to radiomic value (empty at orchestration layer).

        Raises:
            ValueError: If image_path or mask_path is empty.
            TypeError: If feature_classes is not list/tuple or contains non-strings.
        """
        for label, value in (
            ("image_path", image_path),
            ("mask_path", mask_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"RadiomicsExtractor: {label} must be a non-empty string")
        if not isinstance(feature_classes, (list, tuple)):
            raise TypeError("RadiomicsExtractor: feature_classes must be list/tuple")
        for fc in feature_classes:
            if not isinstance(fc, str):
                raise TypeError("RadiomicsExtractor: every feature class must be a string")
        return {}
