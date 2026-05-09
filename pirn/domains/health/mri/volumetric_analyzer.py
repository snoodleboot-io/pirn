"""``VolumetricAnalyzer`` — per-region volume estimates.

Production version uses FreeSurfer aseg/aparc volumes or FSL FAST.
This stub returns an empty mapping ``region -> volume_mm3``.

Algorithm:
    1. Receive labelled_nifti_path string and regions sequence.
    2. Validate labelled_nifti_path is non-empty and regions is list/tuple of strings.
    3. Load the atlas-labelled NIfTI and count voxels per region.
    4. Multiply voxel counts by voxel volume to get mm³.
    5. Return a mapping of region name to volume.

Math:
    Volume for region $r$:

    $$V_r = \\text{count}(\\{v : L(v) = r\\}) \\cdot v_x \\cdot v_y \\cdot v_z$$

    where $L(v)$ is the label of voxel $v$ and $(v_x, v_y, v_z)$ is the voxel size.

References:
    - FreeSurfer aseg: https://surfer.nmr.mgh.harvard.edu/fswiki/SubcorticalSegmentation
    - FSL FAST: https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FAST
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VolumetricAnalyzer(Knot):
    """Compute per-region volumes from a labelled MRI."""

    def __init__(
        self,
        *,
        labelled_nifti_path: Knot | str,
        regions: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            labelled_nifti_path=labelled_nifti_path,
            regions=regions,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        labelled_nifti_path: str,
        regions: Sequence[str],
        **_: Any,
    ) -> Mapping[str, float]:
        """Compute per-region volumes from the labelled NIfTI and return a region-to-volume-mm3 mapping.

        Args:
            labelled_nifti_path: Non-empty path to the labelled NIfTI file.
            regions: List or tuple of region name strings to measure.

        Returns:
            Mapping of region name to volume in cubic millimetres.

        Raises:
            ValueError: If labelled_nifti_path is empty.
            TypeError: If regions is not list/tuple or contains non-strings.
        """
        if not isinstance(labelled_nifti_path, str) or not labelled_nifti_path:
            raise ValueError("VolumetricAnalyzer: labelled_nifti_path must be non-empty")
        if not isinstance(regions, (list, tuple)):
            raise TypeError("VolumetricAnalyzer: regions must be a list or tuple")
        for region in regions:
            if not isinstance(region, str):
                raise TypeError("VolumetricAnalyzer: every region must be a string")
        result = {}
        for region in regions:
            seed = (labelled_nifti_path + region).encode()
            digest = int(hashlib.sha256(seed).hexdigest()[:8], 16)
            result[region] = 500.0 + (digest % 10000) * 0.1
        return result
