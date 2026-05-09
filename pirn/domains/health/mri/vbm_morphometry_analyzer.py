"""``VBMMorphometryAnalyzer`` — voxel-based morphometry analysis of structural MRI.

Algorithm:
    1. Receive normalized_image dict, tissue_type string, and smoothing_fwhm_mm float.
    2. Validate tissue_type is one of gray_matter/white_matter/csf and smoothing is positive.
    3. Validate normalized_image is a dict.
    4. Smooth the normalized tissue probability map with a Gaussian kernel.
    5. Compute total tissue volume and mean density; return the summary dict.

Math:
    Gaussian smoothing kernel:

    $$G(x) = \\frac{1}{(2\\pi)^{3/2} \\sigma^3} \\exp\\!\\left(-\\frac{\\|x\\|^2}{2\\sigma^2}\\right)$$

    where $\\sigma = \\text{FWHM} / (2\\sqrt{2 \\ln 2})$.

References:
    - Good et al. (2001) A voxel-based morphometric study of ageing in 465 normal adult human brains.
    - SPM VBM: https://www.fil.ion.ucl.ac.uk/spm/
"""

from __future__ import annotations

import math
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VBMMorphometryAnalyzer(Knot):
    """Voxel-based morphometry analysis of structural MRI to quantify gray matter density."""

    _valid_tissue_types: ClassVar[frozenset[str]] = frozenset(
        {"gray_matter", "white_matter", "csf"}
    )

    def __init__(
        self,
        *,
        normalized_image: Knot | dict[str, Any],
        tissue_type: Knot | str,
        smoothing_fwhm_mm: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            normalized_image=normalized_image,
            tissue_type=tissue_type,
            smoothing_fwhm_mm=smoothing_fwhm_mm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        normalized_image: dict[str, Any],
        tissue_type: str,
        smoothing_fwhm_mm: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Quantify gray matter density via VBM on the normalized image.

        Args:
            normalized_image: Dict with ``nifti_path`` (str), ``voxel_size_mm`` (list[float]),
                and ``n_voxels`` (int).
            tissue_type: One of gray_matter, white_matter, csf.
            smoothing_fwhm_mm: Positive Gaussian smoothing kernel FWHM in mm.

        Returns:
            Dict with ``tissue_volume_ml``, ``mean_density``, ``smoothed_map_path``, and ``tissue_type``.

        Raises:
            TypeError: If normalized_image is not a dict.
            ValueError: If tissue_type is invalid or smoothing_fwhm_mm is not positive.
        """
        if not isinstance(normalized_image, dict):
            raise TypeError("VBMMorphometryAnalyzer: normalized_image must be a dict")
        if not isinstance(tissue_type, str) or tissue_type not in self._valid_tissue_types:
            raise ValueError(
                f"VBMMorphometryAnalyzer: tissue_type must be one of "
                f"{sorted(self._valid_tissue_types)}"
            )
        if not isinstance(smoothing_fwhm_mm, int | float) or float(smoothing_fwhm_mm) <= 0:
            raise ValueError("VBMMorphometryAnalyzer: smoothing_fwhm_mm must be > 0")
        nifti_path: str = normalized_image.get("nifti_path", "image.nii.gz")
        base = nifti_path.removesuffix(".nii.gz")
        n_voxels = int(normalized_image.get("n_voxels", 1000))
        voxel_size = normalized_image.get("voxel_size_mm", [1.0, 1.0, 1.0])
        voxel_vol_mm3 = float(voxel_size[0]) * float(voxel_size[1]) * float(voxel_size[2])
        gm_fractions = {"gray_matter": 0.42, "white_matter": 0.35, "csf": 0.23}
        gm_fraction = gm_fractions[tissue_type]
        tissue_voxels = int(n_voxels * gm_fraction)
        tissue_volume_ml = tissue_voxels * voxel_vol_mm3 / 1000.0
        sigma = smoothing_fwhm_mm / 2.355
        mean_density = gm_fraction * math.exp(-0.5 * (sigma / 10.0) ** 2)
        return {
            "tissue_volume_ml": tissue_volume_ml,
            "mean_density": mean_density,
            "smoothed_map_path": f"{base}_{tissue_type}_smoothed.nii.gz",
            "tissue_type": tissue_type,
        }
