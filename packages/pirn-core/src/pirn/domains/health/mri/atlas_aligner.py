"""``AtlasAligner`` — align an MRI to an anatomical atlas.

Production version uses MNI152 / Talairach atlases via ANTs. This stub
returns the requested output path.

Algorithm:
    1. Receive nifti_path, atlas_name, and output_aligned_path strings.
    2. Validate that all are non-empty strings.
    3. Compute affine + nonlinear warp from subject space to atlas space.
    4. Apply the composite transform to the NIfTI volume.
    5. Return the output aligned NIfTI path.


References:
    - ANTs: https://github.com/ANTsX/ANTs
    - Avants et al. (2011) A reproducible evaluation of ANTs similarity metric performance in brain image registration.
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


class AtlasAligner(Knot):
    """Align an MRI volume to a named atlas."""

    def __init__(
        self,
        *,
        nifti_path: Knot | str,
        atlas_name: Knot | str,
        output_aligned_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            nifti_path=nifti_path,
            atlas_name=atlas_name,
            output_aligned_path=output_aligned_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        nifti_path: str,
        atlas_name: str,
        output_aligned_path: str,
        **_: Any,
    ) -> str:
        """Align the NIfTI volume to the configured anatomical atlas and return the output aligned path.

        Args:
            nifti_path: Non-empty path to the input NIfTI file.
            atlas_name: Non-empty atlas identifier string (e.g. MNI152).
            output_aligned_path: Non-empty path for the aligned NIfTI output.

        Returns:
            Path string for the atlas-aligned NIfTI output file.

        Raises:
            ValueError: If any argument is empty or not a non-empty string.
        """
        for label, value in (
            ("nifti_path", nifti_path),
            ("atlas_name", atlas_name),
            ("output_aligned_path", output_aligned_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"AtlasAligner: {label} must be a non-empty string")
        cmd = [
            "antsRegistrationSyNQuick.sh",
            "-d",
            "3",
            "-f",
            nifti_path,
            "-m",
            f"{atlas_name}.nii.gz",
            "-o",
            output_aligned_path,
        ]
        await _run_subprocess(cmd)
        return output_aligned_path
