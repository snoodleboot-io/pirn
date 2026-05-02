"""``WhiteMatterAnalyzer`` — white-matter integrity / FA / MD analysis.

Production version uses FSL DTI / MRtrix. This stub returns an empty
mapping ``tract -> {fa, md}``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class WhiteMatterAnalyzer(Knot):
    """Compute per-tract DTI metrics from a DWI volume."""

    def __init__(
        self,
        *,
        dwi_nifti_path: str,
        bvec_path: str,
        bval_path: str,
        tracts: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("dwi_nifti_path", dwi_nifti_path),
            ("bvec_path", bvec_path),
            ("bval_path", bval_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"WhiteMatterAnalyzer: {label} must be a non-empty string"
                )
        if not isinstance(tracts, (list, tuple)):
            raise TypeError(
                "WhiteMatterAnalyzer: tracts must be list/tuple"
            )
        for tract in tracts:
            if not isinstance(tract, str):
                raise TypeError(
                    "WhiteMatterAnalyzer: every tract must be a string"
                )
        self._dwi_nifti_path = dwi_nifti_path
        self._bvec_path = bvec_path
        self._bval_path = bval_path
        self._tracts = tuple(tracts)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, Mapping[str, float]]:
        return {tract: {"fa": 0.0, "md": 0.0} for tract in self._tracts}
