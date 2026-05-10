"""``MotionCorrector`` — rigid-body motion correction on an MRI volume.

Production version uses FSL MCFLIRT or ``nipype`` realignment. This
stub returns the input NIfTI path unchanged.

Algorithm:
    1. Receive nifti_path and output_nifti_path strings.
    2. Validate that both are non-empty strings.
    3. Estimate 6-DOF rigid-body motion parameters per volume.
    4. Apply realignment transforms to each volume.
    5. Return the motion-corrected output NIfTI path.


References:
    - Jenkinson et al. (2002) Improved optimization for the robust and accurate linear registration and motion correction of brain images.
    - FSL MCFLIRT: https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/MCFLIRT
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

try:
    import ants

    _HAS_ANTS: bool = True
except ImportError:
    ants = None  # type: ignore[assignment]
    _HAS_ANTS = False


def _correct_motion(nifti_path: str, output_nifti_path: str) -> None:
    if not _HAS_ANTS or ants is None:
        raise ImportError(
            "antspyx is required for MotionCorrector — install with: pip install 'pirn[mri]'"
        )
    img = ants.image_read(nifti_path)
    result = ants.motion_correction(img)
    ants.image_write(result["motion_corrected"], output_nifti_path)


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
