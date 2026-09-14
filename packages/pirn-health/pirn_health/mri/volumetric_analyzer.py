"""``VolumetricAnalyzer`` — per-region volume estimates.

Production version uses FreeSurfer aseg/aparc volumes or FSL FAST, loading
the atlas-labelled NIfTI via ``nibabel`` and counting voxels per region. No
synthetic fallback exists: ``process()`` raises ``NotImplementedError`` once
inputs validate rather than inventing plausible-looking volumes from the
input path.

Algorithm:
    1. Receive labelled_nifti_path string and regions sequence.
    2. Validate labelled_nifti_path is non-empty and regions is list/tuple of strings.
    3. Raise ``NotImplementedError`` — real computation requires the 'mri'
       extra (nibabel) to load the labelled NIfTI and count voxels per
       region. There is no fallback path; synthetic values are never produced.

Math:
    Volume for region $r$:

    $$V_r = \\text{count}(\\{v : L(v) = r\\}) \\cdot v_x \\cdot v_y \\cdot v_z$$

    where $L(v)$ is the label of voxel $v$ and $(v_x, v_y, v_z)$ is the voxel size.

References:
    - FreeSurfer aseg: https://surfer.nmr.mgh.harvard.edu/fswiki/SubcorticalSegmentation
    - FSL FAST: https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FAST

Note:
    ``_is_stub`` is ``True`` on this knot: it is a functional placeholder
    for the production implementation described above, not a complete
    algorithm. It is registered so pipelines can be wired and tested
    end-to-end before the real implementation lands; do not treat its
    output as production-quality.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VolumetricAnalyzer(Knot):
    """Compute per-region volumes from a labelled MRI."""

    _is_stub: ClassVar[bool] = True

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
            Never returns; always raises ``NotImplementedError``.

        Raises:
            ValueError: If labelled_nifti_path is empty.
            TypeError: If regions is not list/tuple or contains non-strings.
            NotImplementedError: Always, once inputs validate — real volumetric
                computation requires the 'mri' extra (nibabel); no synthetic
                fallback exists.
        """
        if not isinstance(labelled_nifti_path, str) or not labelled_nifti_path:
            raise ValueError("VolumetricAnalyzer: labelled_nifti_path must be non-empty")
        if not isinstance(regions, (list, tuple)):
            raise TypeError("VolumetricAnalyzer: regions must be a list or tuple")
        for region in regions:
            if not isinstance(region, str):
                raise TypeError("VolumetricAnalyzer: every region must be a string")
        raise NotImplementedError(
            "VolumetricAnalyzer: real computation requires the 'mri' extra (nibabel); "
            "synthetic values are not produced"
        )
