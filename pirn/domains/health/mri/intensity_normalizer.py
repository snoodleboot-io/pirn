"""``IntensityNormalizer`` — z-score / WhiteStripe intensity normaliser.

Production version uses ``intensity-normalization`` (zscore, fcm,
whitestripe). This stub validates inputs and returns the output path.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class IntensityNormalizer(Knot):
    """Normalise MRI intensities to a common scale."""

    def __init__(
        self,
        *,
        nifti_path: str,
        method: str,
        output_nifti_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("nifti_path", nifti_path),
            ("method", method),
            ("output_nifti_path", output_nifti_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"IntensityNormalizer: {label} must be a non-empty string"
                )
        if method not in ("zscore", "whitestripe", "fcm"):
            raise ValueError(
                "IntensityNormalizer: method must be one of zscore/whitestripe/fcm"
            )
        self._nifti_path = nifti_path
        self._method = method
        self._output_nifti_path = output_nifti_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        """Normalise MRI intensities using the configured method and return the output NIfTI path.

        Returns:
            Path string for the intensity-normalised NIfTI output file.
        """
        return self._output_nifti_path
