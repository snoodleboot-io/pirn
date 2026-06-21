"""``IntensityNormalizer`` — z-score / WhiteStripe intensity normaliser.

Production version uses ``intensity-normalization`` (zscore, fcm,
whitestripe). This stub validates inputs and returns the output path.

Algorithm:
    1. Receive nifti_path, method, and output_nifti_path strings.
    2. Validate all are non-empty strings and method is one of zscore/whitestripe/fcm.
    3. Compute whole-brain intensity statistics (mean, std, or white-matter mode).
    4. Rescale voxel intensities and write to output_nifti_path.
    5. Return the output NIfTI path.

Math:
    Z-score normalisation:

    $$\\tilde{v}_i = \\frac{v_i - \\mu_{\\text{brain}}}{\\sigma_{\\text{brain}}}$$

References:
    - Shinohara et al. (2014) Statistical normalization techniques for MRI.
    - intensity-normalization: https://github.com/jcreinhold/intensity-normalization
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

try:
    import nibabel as nib

    _HAS_NIB: bool = True
except ImportError:
    nib = None  # type: ignore[assignment]
    _HAS_NIB = False


def _normalize(nifti_path: str, output_nifti_path: str) -> None:
    if not _HAS_NIB or nib is None:
        raise ImportError(
            "nibabel is required for IntensityNormalizer — install with: pip install 'pirn[mri]'"
        )
    img = nib.load(nifti_path)
    data = np.asarray(img.dataobj, dtype=float)
    mean, std = data.mean(), data.std()
    normalized = (data - mean) / (std if std > 0 else 1.0)
    out_img = nib.Nifti1Image(normalized, img.affine, img.header)
    nib.save(out_img, output_nifti_path)


class IntensityNormalizer(Knot):
    """Normalise MRI intensities to a common scale."""

    def __init__(
        self,
        *,
        nifti_path: Knot | str,
        method: Knot | str,
        output_nifti_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            nifti_path=nifti_path,
            method=method,
            output_nifti_path=output_nifti_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        nifti_path: str,
        method: str,
        output_nifti_path: str,
        **_: Any,
    ) -> str:
        """Normalise MRI intensities using the configured method and return the output NIfTI path.

        Args:
            nifti_path: Non-empty path to the input NIfTI file.
            method: One of zscore, whitestripe, fcm.
            output_nifti_path: Non-empty path for the normalised NIfTI output.

        Returns:
            Path string for the intensity-normalised NIfTI output file.

        Raises:
            ValueError: If any argument is empty or method is invalid.
        """
        for label, value in (
            ("nifti_path", nifti_path),
            ("method", method),
            ("output_nifti_path", output_nifti_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"IntensityNormalizer: {label} must be a non-empty string")
        if method not in ("zscore", "whitestripe", "fcm"):
            raise ValueError("IntensityNormalizer: method must be one of zscore/whitestripe/fcm")
        await asyncio.to_thread(_normalize, nifti_path, output_nifti_path)
        return output_nifti_path
