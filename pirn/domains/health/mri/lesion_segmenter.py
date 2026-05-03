"""``LesionSegmenter`` — lesion-segmentation model inference.

Production version uses an nnU-Net / MONAI deep model. This stub
returns the requested segmentation output path.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class LesionSegmenter(Knot):
    """Segment lesions from a preprocessed MRI."""

    def __init__(
        self,
        *,
        nifti_path: str,
        model_name: str,
        output_segmentation_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("nifti_path", nifti_path),
            ("model_name", model_name),
            ("output_segmentation_path", output_segmentation_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"LesionSegmenter: {label} must be a non-empty string"
                )
        self._nifti_path = nifti_path
        self._model_name = model_name
        self._output_segmentation_path = output_segmentation_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        """Run the configured lesion-segmentation model on the NIfTI input and return the segmentation output path.

        Returns:
            Path string for the lesion segmentation output file.
        """
        return self._output_segmentation_path
