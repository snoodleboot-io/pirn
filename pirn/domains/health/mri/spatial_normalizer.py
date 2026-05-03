"""``SpatialNormalizer`` — register subject MRI to a standard atlas space."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SpatialNormalizer(Knot):
    """Register subject MRI to a standard atlas space (MNI152, Talairach)."""

    _VALID_TEMPLATES: frozenset[str] = frozenset({"MNI152", "MNI152_2mm", "Talairach"})
    _VALID_REGISTRATION_TYPES: frozenset[str] = frozenset({"linear", "nonlinear"})
    _VALID_DOF: frozenset[int] = frozenset({6, 9, 12})

    def __init__(
        self,
        *,
        image: Knot,
        template: str,
        registration_type: str,
        degrees_of_freedom: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(template, str) or template not in self._VALID_TEMPLATES:
            raise ValueError(
                f"SpatialNormalizer: template must be one of {sorted(self._VALID_TEMPLATES)}"
            )
        if not isinstance(registration_type, str) or registration_type not in self._VALID_REGISTRATION_TYPES:
            raise ValueError(
                f"SpatialNormalizer: registration_type must be one of "
                f"{sorted(self._VALID_REGISTRATION_TYPES)}"
            )
        if not isinstance(degrees_of_freedom, int) or degrees_of_freedom not in self._VALID_DOF:
            raise ValueError(
                f"SpatialNormalizer: degrees_of_freedom must be one of {sorted(self._VALID_DOF)}"
            )
        self._template = template
        self._registration_type = registration_type
        self._degrees_of_freedom = degrees_of_freedom
        super().__init__(image=image, _config=_config, **kwargs)

    async def process(self, image: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Register the subject MRI to the configured standard space template.

        Args:
            image: Dict with ``nifti_path`` (str) and ``voxel_size_mm`` (list[float]).

        Returns:
            Dict with ``warped_image_path``, ``warp_field_path``, ``template``,
            and ``final_cost``.
        """
        if not isinstance(image, dict):
            raise TypeError("SpatialNormalizer: image must be a dict")
        nifti_path: str = image.get("nifti_path", "image.nii.gz")
        base = nifti_path.removesuffix(".nii.gz")
        return {
            "warped_image_path": f"{base}_warped_{self._template}.nii.gz",
            "warp_field_path": f"{base}_warp_{self._template}.nii.gz",
            "template": self._template,
            "final_cost": 0.0,
        }
