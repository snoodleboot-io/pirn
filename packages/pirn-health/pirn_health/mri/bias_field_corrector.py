# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``BiasFieldCorrector`` — N4 bias-field correction.

Production version uses ANTs N4BiasFieldCorrection or
``SimpleITK.N4BiasFieldCorrectionImageFilter``. This stub validates
inputs and returns the requested output path.

Algorithm:
    1. Receive nifti_path and output_nifti_path strings.
    2. Validate that both are non-empty strings.
    3. Estimate the slow-varying bias field using B-spline fitting.
    4. Divide the input image by the estimated field.
    5. Return the path to the corrected NIfTI output.

Math:
    N4 multiplicative field model:

    $$y = x \\cdot f + n$$

    where $y$ is the observed signal, $x$ the true signal, $f$ the bias field, $n$ noise.

References:
    - Tustison et al. (2010) N4ITK: Improved N3 Bias Correction.
    - SimpleITK: https://simpleitk.readthedocs.io/

Note:
    ``_is_stub`` is ``True`` on this knot: it is a functional placeholder
    for the production implementation described above, not a complete
    algorithm. It is registered so pipelines can be wired and tested
    end-to-end before the real implementation lands; do not treat its
    output as production-quality.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.health_optional_dependency import HealthOptionalDependency


class BiasFieldCorrector(Knot):
    """Apply N4 bias-field correction to an MRI NIfTI file."""

    _is_stub: ClassVar[bool] = True

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
        """Apply N4 bias-field correction to the NIfTI volume and return the corrected output path.

        Args:
            nifti_path: Non-empty path to the input NIfTI file.
            output_nifti_path: Non-empty path for the corrected NIfTI output.

        Returns:
            Path string for the bias-field-corrected NIfTI output file.

        Raises:
            ValueError: If either argument is empty or not a non-empty string.
        """
        for label, value in (
            ("nifti_path", nifti_path),
            ("output_nifti_path", output_nifti_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"BiasFieldCorrector: {label} must be a non-empty string")
        await asyncio.to_thread(self._apply_n4, nifti_path, output_nifti_path)
        return output_nifti_path

    @staticmethod
    def _apply_n4(nifti_path: str, output_nifti_path: str) -> None:
        sitk = HealthOptionalDependency.require("SimpleITK", extra="mri")
        img = sitk.ReadImage(nifti_path, sitk.sitkFloat32)
        corrector = sitk.N4BiasFieldCorrectionImageFilter()
        corrected = corrector.Execute(img)
        sitk.WriteImage(corrected, output_nifti_path)
