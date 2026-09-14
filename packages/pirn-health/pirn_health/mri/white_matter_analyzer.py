# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``WhiteMatterAnalyzer`` — white-matter integrity / FA / MD analysis.

Production version uses dipy + nibabel for DTI fitting.

Algorithm:
    1. Receive dwi_nifti_path, bvec_path, bval_path strings, and tracts sequence.
    2. Validate all paths are non-empty and tracts is list/tuple of strings.
    3. Fit diffusion tensor model to DWI data.
    4. Extract FA and MD maps from tensor eigenvalues.
    5. Summarise per-tract mean FA and MD and return the mapping.

Math:
    Fractional anisotropy:

    $$FA = \\sqrt{\\frac{3}{2}} \\frac{\\sqrt{(\\lambda_1 - \\bar{\\lambda})^2 + (\\lambda_2 - \\bar{\\lambda})^2 + (\\lambda_3 - \\bar{\\lambda})^2}}{\\sqrt{\\lambda_1^2 + \\lambda_2^2 + \\lambda_3^2}}$$

References:
    - Basser et al. (1994) MR diffusion tensor spectroscopy and imaging.
    - dipy: https://dipy.org/
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.health_optional_dependency import HealthOptionalDependency


class WhiteMatterAnalyzer(Knot):
    """Compute per-tract DTI metrics from a DWI volume."""

    def __init__(
        self,
        *,
        dwi_nifti_path: Knot | str,
        bvec_path: Knot | str,
        bval_path: Knot | str,
        tracts: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dwi_nifti_path=dwi_nifti_path,
            bvec_path=bvec_path,
            bval_path=bval_path,
            tracts=tracts,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dwi_nifti_path: str,
        bvec_path: str,
        bval_path: str,
        tracts: Sequence[str],
        **_: Any,
    ) -> Mapping[str, Mapping[str, float]]:
        """Compute FA and MD metrics per tract from the DWI volume and return a tract-to-metrics mapping.

        Args:
            dwi_nifti_path: Non-empty path to the DWI NIfTI file.
            bvec_path: Non-empty path to the b-vector file.
            bval_path: Non-empty path to the b-value file.
            tracts: List or tuple of tract name strings to analyse.

        Returns:
            Mapping of tract name to a dict with ``fa`` and ``md`` float values.

        Raises:
            ValueError: If any path is empty.
            TypeError: If tracts is not list/tuple or contains non-strings.
        """
        for label, value in (
            ("dwi_nifti_path", dwi_nifti_path),
            ("bvec_path", bvec_path),
            ("bval_path", bval_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"WhiteMatterAnalyzer: {label} must be a non-empty string")
        if not isinstance(tracts, (list, tuple)):
            raise TypeError("WhiteMatterAnalyzer: tracts must be list/tuple")
        for tract in tracts:
            if not isinstance(tract, str):
                raise TypeError("WhiteMatterAnalyzer: every tract must be a string")
        return await asyncio.to_thread(
            self._fit_dti, dwi_nifti_path, bvec_path, bval_path, list(tracts)
        )

    @staticmethod
    def _fit_dti(
        dwi_nifti_path: str,
        bvec_path: str,
        bval_path: str,
        tracts: list[str],
    ) -> dict[str, dict[str, float]]:
        nib = HealthOptionalDependency.require("nibabel", extra="mri")
        gradients = HealthOptionalDependency.require("dipy.core.gradients", extra="mri")
        dti = HealthOptionalDependency.require("dipy.reconst.dti", extra="mri")
        img = nib.load(dwi_nifti_path)
        data: np.ndarray = np.asarray(img.dataobj, dtype=float)
        bvecs: np.ndarray = np.loadtxt(bvec_path)
        bvals: np.ndarray = np.loadtxt(bval_path)
        gtab = gradients.gradient_table(bvals, bvecs=bvecs)
        model = dti.TensorModel(gtab)
        fit = model.fit(data)
        fa: np.ndarray = np.asarray(fit.fa)
        md: np.ndarray = np.asarray(fit.md)
        mean_fa = float(np.nanmean(fa))
        mean_md = float(np.nanmean(md))
        return {tract: {"fa": mean_fa, "md": mean_md} for tract in tracts}
