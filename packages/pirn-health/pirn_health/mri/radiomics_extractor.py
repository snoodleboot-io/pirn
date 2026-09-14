# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``RadiomicsExtractor`` — pyradiomics-style radiomic feature extractor.

Production version uses ``pyradiomics`` to compute first-order, texture, and
shape features from an image and ROI mask. No synthetic fallback exists:
``pyradiomics`` is not part of any current ``pirn-health`` extra, so
``process()`` raises ``NotImplementedError`` unconditionally rather than
inventing plausible-looking feature values from the input paths.

Algorithm:
    1. Receive image_path, mask_path strings, and feature_classes sequence.
    2. Validate paths are non-empty and feature_classes is list/tuple of strings.
    3. Raise ``NotImplementedError`` — real computation requires ``pyradiomics``
       to load the image/mask pair and compute the requested feature classes.
       There is no fallback path; synthetic values are never produced.

Math:
    Grey-level co-occurrence matrix (GLCM) contrast:

    $$\\text{Contrast} = \\sum_{i,j} (i - j)^2 P(i,j)$$

References:
    - van Griethuysen et al. (2017) Computational Radiomics System to Decode the Radiographic Phenotype.
    - pyradiomics: https://pyradiomics.readthedocs.io/

Note:
    ``_is_stub`` is ``True`` on this knot: it is a functional placeholder
    for the production implementation described above, not a complete
    algorithm. It is registered so pipelines can be wired and tested
    end-to-end before the real implementation lands; do not treat its
    output as production-quality.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RadiomicsExtractor(Knot):
    """Extract radiomic features from an image and ROI mask."""

    _is_stub: ClassVar[bool] = True

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
            Never returns; always raises ``NotImplementedError``.

        Raises:
            ValueError: If image_path or mask_path is empty.
            TypeError: If feature_classes is not list/tuple or contains non-strings.
            NotImplementedError: Always, once inputs validate — real radiomic
                computation requires ``pyradiomics``; no synthetic fallback exists.
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
        raise NotImplementedError(
            "RadiomicsExtractor: real computation requires 'pyradiomics' "
            "(not currently part of any pirn-health extra); synthetic values are not produced"
        )
