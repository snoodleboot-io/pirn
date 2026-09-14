# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``MotionCorrector`` — rigid-body motion correction on an MRI volume.

Uses dipy ``motion_correction`` for volume-to-volume realignment without antspyx.

Algorithm:
    1. Receive nifti_path and output_nifti_path strings.
    2. Validate that both are non-empty strings.
    3. Estimate 6-DOF rigid-body motion parameters per volume.
    4. Apply realignment transforms to each volume.
    5. Return the motion-corrected output NIfTI path.


References:
    - Garyfallidis et al. (2014) Dipy, a library for the analysis of diffusion MRI data.
    - Jenkinson et al. (2002) Improved optimization for the robust and accurate linear registration.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.health_optional_dependency import HealthOptionalDependency


class MotionCorrector(Knot):
    """Apply motion correction to an MRI NIfTI file."""

    def __init__(
        self,
        *,
        nifti_path: Knot | str,
        output_nifti_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            nifti_path=nifti_path,
            output_nifti_path=output_nifti_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        nifti_path: str,
        output_nifti_path: str,
        **_: Any,
    ) -> str:
        """Apply rigid-body motion correction to the NIfTI volume and return the corrected output path.

        Args:
            nifti_path: Non-empty path to the input NIfTI file.
            output_nifti_path: Non-empty path for the motion-corrected NIfTI output.

        Returns:
            Path string for the motion-corrected NIfTI output file.

        Raises:
            ValueError: If either argument is empty or not a non-empty string.
        """
        for label, value in (
            ("nifti_path", nifti_path),
            ("output_nifti_path", output_nifti_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"MotionCorrector: {label} must be a non-empty string")
        await asyncio.to_thread(self._correct_motion, nifti_path, output_nifti_path)
        return output_nifti_path

    @staticmethod
    def _correct_motion(nifti_path: str, output_nifti_path: str) -> None:
        nib = HealthOptionalDependency.require("nibabel", extra="mri")
        imaffine = HealthOptionalDependency.require("dipy.align.imaffine", extra="mri")
        transforms = HealthOptionalDependency.require("dipy.align.transforms", extra="mri")
        img = nib.load(nifti_path)
        data: np.ndarray = np.asarray(img.dataobj)

        if data.ndim == 3:
            nib.save(img, output_nifti_path)
            return

        affine: np.ndarray = np.asarray(img.affine)
        reference: np.ndarray = data[..., 0]
        corrected: np.ndarray = np.empty_like(data)
        corrected[..., 0] = reference

        metric = imaffine.MutualInformationMetric(nbins=32, sampling_proportion=None)
        affreg = imaffine.AffineRegistration(
            metric=metric, level_iters=[10000, 1000, 100], sigmas=[3.0, 1.0, 0.0], factors=[4, 2, 1]
        )
        transform = transforms.RigidTransform3D()

        volume_count: int = data.shape[-1]
        for vol in range(1, volume_count):
            moving: np.ndarray = data[..., vol]
            mapping = affreg.optimize(
                reference,
                moving,
                transform,
                None,
                static_grid2world=affine,
                moving_grid2world=affine,
            )
            corrected[..., vol] = mapping.transform(moving)

        out_img = nib.Nifti1Image(corrected, affine, img.header)
        nib.save(out_img, output_nifti_path)
