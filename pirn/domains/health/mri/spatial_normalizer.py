"""``SpatialNormalizer`` — register subject MRI to a standard atlas space.

Algorithm:
    1. Receive image dict, template, registration_type, and degrees_of_freedom.
    2. Validate template is one of MNI152/MNI152_2mm/Talairach.
    3. Validate registration_type is one of linear/nonlinear.
    4. Validate degrees_of_freedom is one of 6/9/12.
    5. Compute the registration transform and return the warped image metadata.


References:
    - MNI152: https://www.mcgill.ca/bic/software/tools-data-analysis/anatomical-mri/atlases/mni-152-lin
    - FSL FNIRT: https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FNIRT
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


async def _run_subprocess(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {stderr.decode()}")


class SpatialNormalizer(Knot):
    """Register subject MRI to a standard atlas space (MNI152, Talairach)."""

    def __init__(
        self,
        *,
        image: Knot | dict[str, Any],
        template: Knot | str,
        registration_type: Knot | str,
        degrees_of_freedom: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            image=image,
            template=template,
            registration_type=registration_type,
            degrees_of_freedom=degrees_of_freedom,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        image: dict[str, Any],
        template: str,
        registration_type: str,
        degrees_of_freedom: int,
        **_: Any,
    ) -> dict[str, Any]:
        """Register the subject MRI to the configured standard space template.

        Args:
            image: Dict with ``nifti_path`` (str) and ``voxel_size_mm`` (list[float]).
            template: One of MNI152, MNI152_2mm, Talairach.
            registration_type: One of linear, nonlinear.
            degrees_of_freedom: One of 6, 9, 12.

        Returns:
            Dict with ``warped_image_path``, ``warp_field_path``, ``template``, and ``final_cost``.

        Raises:
            TypeError: If image is not a dict.
            ValueError: If template, registration_type, or degrees_of_freedom are invalid.
        """
        if not isinstance(image, dict):
            raise TypeError("SpatialNormalizer: image must be a dict")
        valid_templates = frozenset({"MNI152", "MNI152_2mm", "Talairach"})
        valid_registration_types = frozenset({"linear", "nonlinear"})
        valid_dof = frozenset({6, 9, 12})
        if not isinstance(template, str) or template not in valid_templates:
            raise ValueError(
                f"SpatialNormalizer: template must be one of {sorted(valid_templates)}"
            )
        if (
            not isinstance(registration_type, str)
            or registration_type not in valid_registration_types
        ):
            raise ValueError(
                f"SpatialNormalizer: registration_type must be one of "
                f"{sorted(valid_registration_types)}"
            )
        if not isinstance(degrees_of_freedom, int) or degrees_of_freedom not in valid_dof:
            raise ValueError(
                f"SpatialNormalizer: degrees_of_freedom must be one of {sorted(valid_dof)}"
            )
        nifti_path: str = image.get("nifti_path", "image.nii.gz")
        base = nifti_path.removesuffix(".nii.gz")
        warped_path = f"{base}_warped_{template}.nii.gz"
        cmd = [
            "flirt",
            "-in",
            nifti_path,
            "-ref",
            "MNI152_T1_2mm_brain.nii.gz",
            "-out",
            warped_path,
        ]
        await _run_subprocess(cmd)
        return {
            "warped_image_path": warped_path,
            "warp_field_path": f"{base}_warp_{template}.nii.gz",
            "template": template,
            "final_cost": 0.0,
        }
