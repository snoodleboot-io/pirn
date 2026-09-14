# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
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

Note:
    ``_is_stub`` is ``True`` on this knot: it is a functional placeholder
    for the production implementation described above, not a complete
    algorithm. It is registered so pipelines can be wired and tested
    end-to-end before the real implementation lands; do not treat its
    output as production-quality.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.health_optional_dependency import HealthOptionalDependency


class IntensityNormalizer(Knot):
    """Normalise MRI intensities to a common scale."""

    _is_stub: ClassVar[bool] = True

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
        await asyncio.to_thread(self._normalize, nifti_path, output_nifti_path)
        return output_nifti_path

    @staticmethod
    def _normalize(nifti_path: str, output_nifti_path: str) -> None:
        nib = HealthOptionalDependency.require("nibabel", extra="mri")
        img = nib.load(nifti_path)
        data: np.ndarray = np.asarray(img.dataobj, dtype=float)
        mean = float(data.mean())
        std = float(data.std())
        normalized: np.ndarray = (data - mean) / (std if std > 0 else 1.0)
        out_img = nib.Nifti1Image(normalized, img.affine, img.header)
        nib.save(out_img, output_nifti_path)
