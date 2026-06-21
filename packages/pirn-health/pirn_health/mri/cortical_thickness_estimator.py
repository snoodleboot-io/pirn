"""``CorticalThicknessEstimator`` — estimate per-region cortical thickness.

Production version uses FreeSurfer or DiReCT (ANTs). This stub returns
an empty mapping ``region -> thickness_mm``.

Algorithm:
    1. Receive t1_nifti_path string and regions sequence.
    2. Validate t1_nifti_path is non-empty and regions is a list/tuple of strings.
    3. Reconstruct cortical surfaces from the T1w volume.
    4. Measure perpendicular distance between pial and white-matter surfaces per vertex.
    5. Average per vertex to per region and return the mapping.

Math:
    Cortical thickness at vertex $v$:

    $$t_v = \\left\\| p_v^{\\text{pial}} - p_v^{\\text{wm}} \\right\\|_2$$

References:
    - Fischl & Dale (2000) Measuring the thickness of the human cerebral cortex from magnetic resonance images.
    - FreeSurfer: https://surfer.nmr.mgh.harvard.edu/
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
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


def _parse_freesurfer_thickness(regions: Sequence[str]) -> dict[str, float]:
    """Return per-region thickness stubs until real FreeSurfer parsing is implemented."""
    return {region: 0.0 for region in regions}


class CorticalThicknessEstimator(Knot):
    """Estimate cortical thickness per region from a T1w MRI."""

    def __init__(
        self,
        *,
        t1_nifti_path: Knot | str,
        regions: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            t1_nifti_path=t1_nifti_path,
            regions=regions,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        t1_nifti_path: str,
        regions: Sequence[str],
        **_: Any,
    ) -> Mapping[str, float]:
        """Estimate cortical thickness for each configured region and return a region-to-thickness-mm mapping.

        Args:
            t1_nifti_path: Non-empty path to the T1-weighted NIfTI file.
            regions: List or tuple of region name strings to estimate.

        Returns:
            Mapping of region name to cortical thickness in millimetres.

        Raises:
            ValueError: If t1_nifti_path is empty.
            TypeError: If regions is not list/tuple or contains non-strings.
        """
        if not isinstance(t1_nifti_path, str) or not t1_nifti_path:
            raise ValueError("CorticalThicknessEstimator: t1_nifti_path must be non-empty")
        if not isinstance(regions, (list, tuple)):
            raise TypeError("CorticalThicknessEstimator: regions must be list/tuple")
        for region in regions:
            if not isinstance(region, str):
                raise TypeError("CorticalThicknessEstimator: every region must be a string")
        cmd = ["recon-all", "-i", t1_nifti_path, "-all"]
        await _run_subprocess(cmd)
        return await asyncio.to_thread(_parse_freesurfer_thickness, regions)
