"""``RegionOfInterestExtractor`` — extract per-ROI statistics.

Algorithm:
    1. Receive nifti_path, atlas_label_path strings, and roi_labels sequence.
    2. Validate paths are non-empty and roi_labels is list/tuple of ints.
    3. Load the NIfTI image and atlas label volume via nibabel.
    4. For each integer label, mask voxels and compute mean intensity.
    5. Return a mapping of label to mean intensity.

Math:
    Mean intensity for ROI with label $l$:

    $$\\mu_l = \\frac{1}{|\\mathcal{V}_l|} \\sum_{v \\in \\mathcal{V}_l} I(v)$$

References:
    - MNI atlas: https://www.mcgill.ca/bic/software/tools-data-analysis/anatomical-mri/atlases
    - nibabel: https://nipy.org/nibabel/
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import nibabel as nib
import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


def _extract_roi_means(
    nifti_path: str,
    atlas_label_path: str,
    roi_labels: Sequence[int],
) -> dict[int, float]:
    img = nib.load(nifti_path)
    atlas = nib.load(atlas_label_path)
    intensity: np.ndarray = np.asarray(img.get_fdata(), dtype=float)
    labels: np.ndarray = np.asarray(atlas.get_fdata())
    result: dict[int, float] = {}
    for lbl in roi_labels:
        mask = labels == lbl
        result[lbl] = float(intensity[mask].mean()) if mask.any() else 0.0
    return result


class RegionOfInterestExtractor(Knot):
    """Extract per-ROI statistics from an aligned MRI."""

    def __init__(
        self,
        *,
        nifti_path: Knot | str,
        atlas_label_path: Knot | str,
        roi_labels: Knot | Sequence[int],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            nifti_path=nifti_path,
            atlas_label_path=atlas_label_path,
            roi_labels=roi_labels,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        nifti_path: str,
        atlas_label_path: str,
        roi_labels: Sequence[int],
        **_: Any,
    ) -> Mapping[int, float]:
        """Extract mean intensity per ROI label from the atlas-aligned NIfTI.

        Args:
            nifti_path: Non-empty path to the input NIfTI file.
            atlas_label_path: Non-empty path to the atlas label volume.
            roi_labels: List or tuple of integer ROI label identifiers.

        Returns:
            Mapping of integer ROI label to mean intensity value.

        Raises:
            ValueError: If nifti_path or atlas_label_path is empty.
            TypeError: If roi_labels is not list/tuple or contains non-ints.
        """
        for label, value in (
            ("nifti_path", nifti_path),
            ("atlas_label_path", atlas_label_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"RegionOfInterestExtractor: {label} must be a non-empty string")
        if not isinstance(roi_labels, (list, tuple)):
            raise TypeError("RegionOfInterestExtractor: roi_labels must be list/tuple")
        for lbl in roi_labels:
            if not isinstance(lbl, int):
                raise TypeError("RegionOfInterestExtractor: every roi label must be int")
        return await asyncio.to_thread(_extract_roi_means, nifti_path, atlas_label_path, roi_labels)
