"""``AtlasAligner`` — align an MRI to an anatomical atlas.

Production version uses MNI152 / Talairach atlases via ANTs. This stub
returns the requested output path.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class AtlasAligner(Knot):
    """Align an MRI volume to a named atlas."""

    def __init__(
        self,
        *,
        nifti_path: str,
        atlas_name: str,
        output_aligned_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("nifti_path", nifti_path),
            ("atlas_name", atlas_name),
            ("output_aligned_path", output_aligned_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"AtlasAligner: {label} must be a non-empty string"
                )
        self._nifti_path = nifti_path
        self._atlas_name = atlas_name
        self._output_aligned_path = output_aligned_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        """Align the NIfTI volume to the configured anatomical atlas and return the output aligned path.

        Returns:
            Path string for the atlas-aligned NIfTI output file.
        """
        return self._output_aligned_path
