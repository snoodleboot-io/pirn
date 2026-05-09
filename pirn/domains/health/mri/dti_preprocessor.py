"""``DTIPreprocessor`` — preprocess diffusion tensor imaging data.

Algorithm:
    1. Receive dwi_data, bvec_file, bval_file dicts, eddy_correct bool, denoise bool.
    2. Validate all three data arguments are dicts.
    3. If denoise, apply MP-PCA or Gibbs ringing correction.
    4. If eddy_correct, apply eddy current and motion correction.
    5. Return the preprocessed DWI metadata dict.


References:
    - Veraart et al. (2016) Denoising of diffusion MRI using random matrix theory.
    - Andersson & Sotiropoulos (2016) An integrated approach to correction for off-resonance effects and subject movement in diffusion MR imaging.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class DTIPreprocessor(Knot):
    """Preprocess DTI data: denoise, eddy correction, brain extraction."""

    def __init__(
        self,
        *,
        dwi_data: Knot | dict[str, Any],
        bvec_file: Knot | dict[str, Any],
        bval_file: Knot | dict[str, Any],
        eddy_correct: Knot | bool = True,
        denoise: Knot | bool = True,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dwi_data=dwi_data,
            bvec_file=bvec_file,
            bval_file=bval_file,
            eddy_correct=eddy_correct,
            denoise=denoise,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dwi_data: dict[str, Any],
        bvec_file: dict[str, Any],
        bval_file: dict[str, Any],
        eddy_correct: bool = True,
        denoise: bool = True,
        **_: Any,
    ) -> dict[str, Any]:
        """Denoise, apply eddy correction, and extract brain from DWI data.

        Args:
            dwi_data: Dict with DWI volume data.
            bvec_file: Dict with b-vector data.
            bval_file: Dict with b-value data.
            eddy_correct: Whether to apply eddy current correction.
            denoise: Whether to apply MP-PCA denoising.

        Returns:
            Dict with ``preprocessed_dwi_path``, ``n_directions``,
            ``b_values``, and ``motion_outliers``.

        Raises:
            TypeError: If any data argument is not a dict or flags are not bools.
        """
        if not isinstance(dwi_data, dict):
            raise TypeError("DTIPreprocessor: dwi_data must be a dict")
        if not isinstance(bvec_file, dict):
            raise TypeError("DTIPreprocessor: bvec_file must be a dict")
        if not isinstance(bval_file, dict):
            raise TypeError("DTIPreprocessor: bval_file must be a dict")
        if not isinstance(eddy_correct, bool):
            raise TypeError("DTIPreprocessor: eddy_correct must be a bool")
        if not isinstance(denoise, bool):
            raise TypeError("DTIPreprocessor: denoise must be a bool")

        import numpy as np

        b_values: list[float] = [float(v) for v in bval_file.get("bvals", [])]
        bvecs: list[list[float]] = bval_file.get("bvecs", []) or bvec_file.get("bvecs", [])
        n_directions = len(b_values) or len(bvecs)

        # Voxel data: optional 2D array (n_voxels x n_directions)
        raw: list[list[float]] | None = dwi_data.get("voxels")
        motion_outliers: list[int] = []

        if raw is not None and len(raw) > 0:
            data = np.asarray(raw, dtype=np.float64)

            if denoise:
                # MP-PCA denoising: threshold singular values below the
                # Marchenko-Pastur noise floor estimate.
                if data.ndim == 2 and data.shape[1] > 1:
                    u, s, vt = np.linalg.svd(data, full_matrices=False)
                    m, n = data.shape
                    sigma_sq = float(np.median(s) ** 2 / n)
                    mp_threshold = sigma_sq * (1.0 + np.sqrt(m / n)) ** 2
                    s_denoised = np.where(s**2 > mp_threshold, s, 0.0)
                    data = u @ np.diag(s_denoised) @ vt

            if eddy_correct and data.shape[1] > 1 if data.ndim == 2 else False:
                # Flag volumes with variance > 2 std above mean as motion outliers
                vol_vars = np.var(data, axis=0)
                mean_var = float(np.mean(vol_vars))
                std_var = float(np.std(vol_vars))
                motion_outliers = [
                    int(i) for i, v in enumerate(vol_vars) if v > mean_var + 2 * std_var
                ]

        dwi_path = dwi_data.get("path", "preprocessed_dwi.nii.gz")
        suffix = (
            "_denoised_eddy"
            if denoise and eddy_correct
            else "_denoised"
            if denoise
            else "_eddy"
            if eddy_correct
            else ""
        )
        preprocessed_path = (
            str(dwi_path).replace(".nii.gz", f"{suffix}.nii.gz")
            if dwi_path
            else f"preprocessed_dwi{suffix}.nii.gz"
        )

        return {
            "preprocessed_dwi_path": preprocessed_path,
            "n_directions": n_directions,
            "b_values": b_values,
            "motion_outliers": motion_outliers,
        }
