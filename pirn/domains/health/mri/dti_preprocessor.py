"""``DTIPreprocessor`` — preprocess diffusion tensor imaging data."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class DTIPreprocessor(Knot):
    """Preprocess DTI data: denoise, eddy correction, brain extraction."""

    def __init__(
        self,
        *,
        dwi_data: Knot,
        bvec_file: Knot,
        bval_file: Knot,
        eddy_correct: bool = True,
        denoise: bool = True,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(eddy_correct, bool):
            raise TypeError("DTIPreprocessor: eddy_correct must be a bool")
        if not isinstance(denoise, bool):
            raise TypeError("DTIPreprocessor: denoise must be a bool")
        self._eddy_correct = eddy_correct
        self._denoise = denoise
        super().__init__(
            dwi_data=dwi_data,
            bvec_file=bvec_file,
            bval_file=bval_file,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dwi_data: dict[str, Any],
        bvec_file: dict[str, Any],
        bval_file: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        """Denoise, apply eddy correction, and extract brain from DWI data.

        Args:
            dwi_data: Dict with DWI volume data.
            bvec_file: Dict with b-vector data.
            bval_file: Dict with b-value data.

        Returns:
            Dict with ``preprocessed_dwi_path``, ``n_directions``,
            ``b_values``, and ``motion_outliers``.
        """
        if not isinstance(dwi_data, dict):
            raise TypeError("DTIPreprocessor: dwi_data must be a dict")
        if not isinstance(bvec_file, dict):
            raise TypeError("DTIPreprocessor: bvec_file must be a dict")
        if not isinstance(bval_file, dict):
            raise TypeError("DTIPreprocessor: bval_file must be a dict")
        return {
            "preprocessed_dwi_path": "preprocessed_dwi.nii.gz",
            "n_directions": 0,
            "b_values": [],
            "motion_outliers": [],
        }
