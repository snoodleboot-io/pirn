"""``BrainMaskExtractor`` — skull-strip a brain MRI.

Production version uses FSL BET, HD-BET, or SynthStrip. This stub
returns the requested mask output path.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class BrainMaskExtractor(Knot):
    """Produce a binary brain mask from an MRI NIfTI."""

    def __init__(
        self,
        *,
        nifti_path: str,
        output_mask_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("nifti_path", nifti_path),
            ("output_mask_path", output_mask_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"BrainMaskExtractor: {label} must be a non-empty string"
                )
        self._nifti_path = nifti_path
        self._output_mask_path = output_mask_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        return self._output_mask_path
