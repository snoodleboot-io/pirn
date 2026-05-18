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

try:
    import nibabel as nib
    from dipy.align.imaffine import AffineRegistration, MutualInformationMetric
    from dipy.align.transforms import RigidTransform3D

    _HAS_DIPY: bool = True
except ImportError:
    nib = None  # type: ignore[assignment]
    AffineRegistration = None  # type: ignore[assignment]
    MutualInformationMetric = None  # type: ignore[assignment]
    RigidTransform3D = None  # type: ignore[assignment]
    _HAS_DIPY = False


def _correct_motion(nifti_path: str, output_nifti_path: str) -> None:
    if (
        not _HAS_DIPY
        or nib is None
        or MutualInformationMetric is None
        or AffineRegistration is None
        or RigidTransform3D is None
    ):
        raise ImportError(
            "nibabel and dipy are required for MotionCorrector — install with: pip install 'pirn[mri]'"
        )
    assert MutualInformationMetric is not None
    assert AffineRegistration is not None
    assert RigidTransform3D is not None
    img = nib.load(nifti_path)
    data = np.asarray(img.dataobj)

    if data.ndim == 3:
        nib.save(img, output_nifti_path)
        return

    affine = img.affine
    reference = data[..., 0]
    corrected = np.empty_like(data)
    corrected[..., 0] = reference

    metric = MutualInformationMetric(nbins=32, sampling_proportion=None)
    affreg = AffineRegistration(
        metric=metric, level_iters=[10000, 1000, 100], sigmas=[3.0, 1.0, 0.0], factors=[4, 2, 1]
    )
    transform = RigidTransform3D()

    for vol in range(1, data.shape[-1]):
        moving = data[..., vol]
        mapping = affreg.optimize(reference, moving, transform, None, affine, affine)
        corrected[..., vol] = mapping.transform(moving)

    out_img = nib.Nifti1Image(corrected, affine, img.header)
    nib.save(out_img, output_nifti_path)


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
        await asyncio.to_thread(_correct_motion, nifti_path, output_nifti_path)
        return output_nifti_path
