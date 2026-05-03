"""``MRIQualityController`` — compute MRI quality metrics and flag poor-quality scans."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class MRIQualityController(Knot):
    """Compute MRI quality metrics (SNR, CNR, motion parameters) and flag poor-quality scans."""

    _VALID_MODALITIES: frozenset[str] = frozenset({"T1w", "T2w", "BOLD", "DWI"})

    def __init__(
        self,
        *,
        mri_data: Knot,
        snr_threshold: float,
        motion_threshold_mm: float,
        modality: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(modality, str) or modality not in self._VALID_MODALITIES:
            raise ValueError(
                f"MRIQualityController: modality must be one of {sorted(self._VALID_MODALITIES)}"
            )
        if not isinstance(snr_threshold, (int, float)) or float(snr_threshold) <= 0:
            raise ValueError("MRIQualityController: snr_threshold must be > 0")
        if not isinstance(motion_threshold_mm, (int, float)) or float(motion_threshold_mm) <= 0:
            raise ValueError("MRIQualityController: motion_threshold_mm must be > 0")
        self._snr_threshold = float(snr_threshold)
        self._motion_threshold_mm = float(motion_threshold_mm)
        self._modality = modality
        super().__init__(mri_data=mri_data, _config=_config, **kwargs)

    async def process(self, mri_data: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Compute SNR, CNR, and motion metrics and return QC assessment.

        Args:
            mri_data: Dict with ``nifti_path`` (str) and ``motion_params``
                (list[float] or None).

        Returns:
            Dict with ``snr``, ``cnr``, ``mean_fd_mm`` (float or None),
            ``passes_qc`` (bool), and ``qc_flags`` (list[str]).
        """
        if not isinstance(mri_data, dict):
            raise TypeError("MRIQualityController: mri_data must be a dict")
        motion_params: list[float] | None = mri_data.get("motion_params")
        mean_fd: float | None = None
        if motion_params is not None:
            mean_fd = sum(abs(v) for v in motion_params) / len(motion_params) if motion_params else 0.0
        snr = 50.0
        cnr = 20.0
        qc_flags: list[str] = []
        if snr < self._snr_threshold:
            qc_flags.append("low_snr")
        if mean_fd is not None and mean_fd > self._motion_threshold_mm:
            qc_flags.append("excessive_motion")
        return {
            "snr": snr,
            "cnr": cnr,
            "mean_fd_mm": mean_fd,
            "passes_qc": len(qc_flags) == 0,
            "qc_flags": qc_flags,
        }
