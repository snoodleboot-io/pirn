"""``BrainMaskExtractor`` — skull-strip a brain MRI.

Uses dipy ``median_otsu`` for robust brain extraction without antspyx.

Algorithm:
    1. Receive nifti_path and output_mask_path strings.
    2. Validate that both are non-empty strings.
    3. Apply median_otsu to isolate brain tissue.
    4. Write the binary brain mask to output_mask_path.
    5. Return the output mask path.


References:
    - Garyfallidis et al. (2014) Dipy, a library for the analysis of diffusion MRI data.
    - Descoteaux et al. (2008) Automatic human brain extraction.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

try:
    import nibabel as nib
    from dipy.segment.mask import median_otsu

    _HAS_DIPY: bool = True
except ImportError:
    nib = None  # type: ignore[assignment]
    median_otsu = None  # type: ignore[assignment]
    _HAS_DIPY = False


def _extract_mask(nifti_path: str, output_mask_path: str) -> None:
    if not _HAS_DIPY or nib is None or median_otsu is None:
        raise ImportError(
            "nibabel and dipy are required for BrainMaskExtractor — install with: pip install 'pirn[mri]'"
        )
    img = nib.load(nifti_path)
    data = np.asarray(img.dataobj)
    _, mask = median_otsu(data)
    mask_img = nib.Nifti1Image(mask.astype(np.uint8), img.affine, img.header)
    nib.save(mask_img, output_mask_path)


class BrainMaskExtractor(Knot):
    """Produce a binary brain mask from an MRI NIfTI."""

    def __init__(
        self,
        *,
        nifti_path: Knot | str,
        output_mask_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            nifti_path=nifti_path,
            output_mask_path=output_mask_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        nifti_path: str,
        output_mask_path: str,
        **_: Any,
    ) -> str:
        """Skull-strip the NIfTI MRI and return the binary brain mask output path.

        Args:
            nifti_path: Non-empty path to the input NIfTI file.
            output_mask_path: Non-empty path for the binary brain mask output.

        Returns:
            Path string for the binary brain mask NIfTI output file.

        Raises:
            ValueError: If either argument is empty or not a non-empty string.
        """
        for label, value in (
            ("nifti_path", nifti_path),
            ("output_mask_path", output_mask_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"BrainMaskExtractor: {label} must be a non-empty string")
        await asyncio.to_thread(_extract_mask, nifti_path, output_mask_path)
        return output_mask_path
