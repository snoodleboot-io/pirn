"""``BiasFieldCorrector`` — N4 bias-field correction.

Production version uses ANTs N4BiasFieldCorrection or
``SimpleITK.N4BiasFieldCorrectionImageFilter``. This stub validates
inputs and returns the requested output path.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class BiasFieldCorrector(Knot):
    """Apply N4 bias-field correction to an MRI NIfTI file."""

    def __init__(
        self,
        *,
        nifti_path: str,
        output_nifti_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("nifti_path", nifti_path),
            ("output_nifti_path", output_nifti_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"BiasFieldCorrector: {label} must be a non-empty string"
                )
        self._nifti_path = nifti_path
        self._output_nifti_path = output_nifti_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        return self._output_nifti_path
