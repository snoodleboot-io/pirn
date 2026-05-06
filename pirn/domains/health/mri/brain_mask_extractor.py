"""``BrainMaskExtractor`` — skull-strip a brain MRI.

Production version uses FSL BET, HD-BET, or SynthStrip. This stub
returns the requested mask output path.

Algorithm:
    1. Receive nifti_path and output_mask_path strings.
    2. Validate that both are non-empty strings.
    3. Apply a skull-stripping algorithm to isolate brain tissue.
    4. Write the binary brain mask to output_mask_path.
    5. Return the output mask path.


References:
    - Smith (2002) Fast robust automated brain extraction. FSL BET.
    - HD-BET: https://github.com/MIC-DKFZ/HD-BET
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
        nifti_path: Knot | str,
        output_mask_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            nifti_path=nifti_path,
            output_mask_path=output_mask_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        nifti_path: str,
        output_mask_path: str,
        **_: Any,
    ) -> str:
        """Skull-strip the NIfTI MRI and return the binary brain mask output path.

        Args:
            nifti_path: Non-empty path to the input NIfTI file.
            output_mask_path: Non-empty path for the binary brain mask output.

        Returns:
            Path string for the binary brain mask NIfTI output file.

        Raises:
            ValueError: If either argument is empty or not a non-empty string.
        """
        for label, value in (
            ("nifti_path", nifti_path),
            ("output_mask_path", output_mask_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"BrainMaskExtractor: {label} must be a non-empty string")
        return output_mask_path
