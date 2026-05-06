"""``ImageRegistrar`` — rigid / affine / nonlinear image registration.

Production version uses ANTs / FSL FLIRT-FNIRT / Elastix. This stub
returns the requested registered-image path.

Algorithm:
    1. Receive moving_path, fixed_path, transform, and output_registered_path strings.
    2. Validate paths are non-empty and transform is one of rigid/affine/syn.
    3. Compute an optimal transform mapping the moving image to the fixed image.
    4. Apply the composite transform and write to output_registered_path.
    5. Return the output registered image path.


References:
    - Avants et al. (2011) A reproducible evaluation of ANTs similarity metric performance.
    - FSL FLIRT: https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FLIRT
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class ImageRegistrar(Knot):
    """Register a moving image to a fixed image."""

    def __init__(
        self,
        *,
        moving_path: Knot | str,
        fixed_path: Knot | str,
        transform: Knot | str,
        output_registered_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            moving_path=moving_path,
            fixed_path=fixed_path,
            transform=transform,
            output_registered_path=output_registered_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        moving_path: str,
        fixed_path: str,
        transform: str,
        output_registered_path: str,
        **_: Any,
    ) -> str:
        """Register the moving image to the fixed image using the configured transform and return the output path.

        Args:
            moving_path: Non-empty path to the moving (source) image.
            fixed_path: Non-empty path to the fixed (target/reference) image.
            transform: One of rigid, affine, syn.
            output_registered_path: Non-empty path for the registered output image.

        Returns:
            Path string for the registered output image file.

        Raises:
            ValueError: If any path is empty or transform is invalid.
        """
        for label, value in (
            ("moving_path", moving_path),
            ("fixed_path", fixed_path),
            ("output_registered_path", output_registered_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"ImageRegistrar: {label} must be a non-empty string")
        if transform not in ("rigid", "affine", "syn"):
            raise ValueError("ImageRegistrar: transform must be one of rigid/affine/syn")
        return output_registered_path
