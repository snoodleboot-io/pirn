"""``MotionCorrector`` — rigid-body motion correction on an MRI volume.

Production version uses FSL MCFLIRT or ``nipype`` realignment. This
stub returns the input NIfTI path unchanged.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class MotionCorrector(Knot):
    """Apply motion correction to an MRI NIfTI file."""

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
                    f"MotionCorrector: {label} must be a non-empty string"
                )
        self._nifti_path = nifti_path
        self._output_nifti_path = output_nifti_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        return self._output_nifti_path
