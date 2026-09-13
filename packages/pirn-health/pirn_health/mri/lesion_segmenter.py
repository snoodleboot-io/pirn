"""``LesionSegmenter`` — lesion-segmentation model inference.

Production version uses an nnU-Net / MONAI deep model. This stub
returns the requested segmentation output path.

Algorithm:
    1. Receive nifti_path, model_name, and output_segmentation_path strings.
    2. Validate all are non-empty strings.
    3. Load the trained segmentation model by model_name.
    4. Run inference over the NIfTI volume in sliding-window patches.
    5. Return the path to the binary lesion mask output.


References:
    - Isensee et al. (2021) nnU-Net: a self-configuring method for deep learning-based biomedical image segmentation.
    - MONAI: https://monai.io/

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


class LesionSegmenter(Knot):
    """Segment lesions from a preprocessed MRI."""

    _is_stub: ClassVar[bool] = True

    def __init__(
        self,
        *,
        nifti_path: Knot | str,
        model_name: Knot | str,
        output_segmentation_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            nifti_path=nifti_path,
            model_name=model_name,
            output_segmentation_path=output_segmentation_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        nifti_path: str,
        model_name: str,
        output_segmentation_path: str,
        **_: Any,
    ) -> str:
        """Run the configured lesion-segmentation model on the NIfTI input and return the segmentation output path.

        Args:
            nifti_path: Non-empty path to the input NIfTI file.
            model_name: Non-empty model identifier string.
            output_segmentation_path: Non-empty path for the segmentation output.

        Returns:
            Path string for the lesion segmentation output file.

        Raises:
            ValueError: If any argument is empty or not a non-empty string.
        """
        for label, value in (
            ("nifti_path", nifti_path),
            ("model_name", model_name),
            ("output_segmentation_path", output_segmentation_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"LesionSegmenter: {label} must be a non-empty string")
        cmd = [
            "nnUNet_predict",
            "-i",
            nifti_path,
            "-o",
            output_segmentation_path,
            "-m",
            model_name,
        ]
        await self._run_subprocess(cmd)
        return output_segmentation_path

    @staticmethod
    async def _run_subprocess(cmd: list[str]) -> None:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"{cmd[0]} failed: {stderr.decode()}")
