"""``VBMMorphometryAnalyzer`` — voxel-based morphometry analysis of structural MRI."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VBMMorphometryAnalyzer(Knot):
    """Voxel-based morphometry analysis of structural MRI to quantify gray matter density."""

    _VALID_TISSUE_TYPES: frozenset[str] = frozenset({"gray_matter", "white_matter", "csf"})

    def __init__(
        self,
        *,
        normalized_image: Knot,
        tissue_type: str,
        smoothing_fwhm_mm: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(tissue_type, str) or tissue_type not in self._VALID_TISSUE_TYPES:
            raise ValueError(
                f"VBMMorphometryAnalyzer: tissue_type must be one of "
                f"{sorted(self._VALID_TISSUE_TYPES)}"
            )
        if not isinstance(smoothing_fwhm_mm, (int, float)) or float(smoothing_fwhm_mm) <= 0:
            raise ValueError("VBMMorphometryAnalyzer: smoothing_fwhm_mm must be > 0")
        self._tissue_type = tissue_type
        self._smoothing_fwhm_mm = float(smoothing_fwhm_mm)
        super().__init__(normalized_image=normalized_image, _config=_config, **kwargs)

    async def process(self, normalized_image: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Quantify gray matter density via VBM on the normalized image.

        Args:
            normalized_image: Dict with ``nifti_path`` (str),
                ``voxel_size_mm`` (list[float]), and ``n_voxels`` (int).

        Returns:
            Dict with ``tissue_volume_ml``, ``mean_density``,
            ``smoothed_map_path``, and ``tissue_type``.
        """
        if not isinstance(normalized_image, dict):
            raise TypeError("VBMMorphometryAnalyzer: normalized_image must be a dict")
        nifti_path: str = normalized_image.get("nifti_path", "image.nii.gz")
        base = nifti_path.removesuffix(".nii.gz")
        return {
            "tissue_volume_ml": 0.0,
            "mean_density": 0.0,
            "smoothed_map_path": f"{base}_{self._tissue_type}_smoothed.nii.gz",
            "tissue_type": self._tissue_type,
        }
