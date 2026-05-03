"""``ImageRegistrar`` — rigid / affine / nonlinear image registration.

Production version uses ANTs / FSL FLIRT-FNIRT / Elastix. This stub
returns the requested registered-image path.
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
        moving_path: str,
        fixed_path: str,
        transform: str,
        output_registered_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("moving_path", moving_path),
            ("fixed_path", fixed_path),
            ("output_registered_path", output_registered_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ImageRegistrar: {label} must be a non-empty string"
                )
        if transform not in ("rigid", "affine", "syn"):
            raise ValueError(
                "ImageRegistrar: transform must be one of rigid/affine/syn"
            )
        self._moving_path = moving_path
        self._fixed_path = fixed_path
        self._transform = transform
        self._output_registered_path = output_registered_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        """Register the moving image to the fixed image using the configured transform and return the output path.

        Returns:
            Path string for the registered output image file.
        """
        return self._output_registered_path
