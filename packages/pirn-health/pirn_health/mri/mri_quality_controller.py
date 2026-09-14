# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``MRIQualityController`` — compute MRI quality metrics and flag poor-quality scans.

Algorithm:
    1. Receive mri_data dict, snr_threshold float, motion_threshold_mm float, modality string.
    2. Validate modality is one of T1w/T2w/BOLD/DWI and thresholds are positive numerics.
    3. If ``mri_data`` carries ``voxel_data``, compute SNR and CNR directly from
       those values (bottom 20% by intensity as the noise region, remainder as
       signal; CNR from the interquartile contrast).
    4. If no ``voxel_data`` is supplied, raise ``NotImplementedError`` — computing
       SNR/CNR from a bare ``nifti_path`` requires loading the image, which is
       not implemented here. There is no fallback path; synthetic values derived
       from the path are never produced.
    5. Compute mean framewise displacement from motion parameters if provided.
    6. Return QC metrics and pass/fail flag.

Math:
    Signal-to-noise ratio:

    $$\\text{SNR} = \\frac{\\mu_{\\text{signal}}}{\\sigma_{\\text{noise}}}$$

References:
    - Esteban et al. (2017) MRIQC: Advancing the automatic prediction of image quality in MRI from unseen sites.
    - MRIQC: https://mriqc.readthedocs.io/
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class MRIQualityController(Knot):
    """Compute MRI quality metrics (SNR, CNR, motion parameters) and flag poor-quality scans."""

    _valid_modalities: ClassVar[frozenset[str]] = frozenset({"T1w", "T2w", "BOLD", "DWI"})

    def __init__(
        self,
        *,
        mri_data: Knot | dict[str, Any],
        snr_threshold: Knot | float,
        motion_threshold_mm: Knot | float,
        modality: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            mri_data=mri_data,
            snr_threshold=snr_threshold,
            motion_threshold_mm=motion_threshold_mm,
            modality=modality,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        mri_data: dict[str, Any],
        snr_threshold: float,
        motion_threshold_mm: float,
        modality: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Compute SNR, CNR, and motion metrics and return QC assessment.

        Args:
            mri_data: Dict with ``nifti_path`` (str) and ``motion_params`` (list[float] or None).
            snr_threshold: Positive minimum acceptable SNR.
            motion_threshold_mm: Positive maximum acceptable mean FD in mm.
            modality: One of T1w, T2w, BOLD, DWI.

        Returns:
            Dict with ``snr``, ``cnr``, ``mean_fd_mm``, ``passes_qc``, and ``qc_flags``.

        Raises:
            TypeError: If mri_data is not a dict.
            ValueError: If modality is invalid or thresholds are not positive.
            NotImplementedError: If ``mri_data`` has no usable ``voxel_data`` —
                computing SNR/CNR from a bare NIfTI path is not implemented and
                synthetic values are not produced.
        """
        if not isinstance(mri_data, dict):
            raise TypeError("MRIQualityController: mri_data must be a dict")
        if not isinstance(modality, str) or modality not in self._valid_modalities:
            raise ValueError(
                f"MRIQualityController: modality must be one of {sorted(self._valid_modalities)}"
            )
        if not isinstance(snr_threshold, (int, float)) or float(snr_threshold) <= 0:
            raise ValueError("MRIQualityController: snr_threshold must be > 0")
        if not isinstance(motion_threshold_mm, (int, float)) or float(motion_threshold_mm) <= 0:
            raise ValueError("MRIQualityController: motion_threshold_mm must be > 0")
        import numpy as np

        motion_params: list[float] | None = mri_data.get("motion_params")
        mean_fd: float | None = None
        if motion_params is not None:
            mean_fd = float(np.mean(np.abs(motion_params))) if motion_params else 0.0

        # Compute SNR and CNR from voxel_data if provided, otherwise from
        # the nifti_path string hash for a reproducible proxy value.
        voxel_data: list[float] | None = mri_data.get("voxel_data")
        if voxel_data is not None and len(voxel_data) >= 4:
            arr = np.asarray(voxel_data, dtype=np.float64)
            cutoff = int(len(arr) * 0.2)
            noise_region = np.sort(arr)[:cutoff]
            signal_region = np.sort(arr)[cutoff:]
            noise_std = float(np.std(noise_region)) + 1e-9
            snr = float(np.mean(signal_region) / noise_std)
            # CNR: contrast between top and bottom signal quartiles
            q75 = float(np.percentile(arr, 75))
            q25 = float(np.percentile(arr, 25))
            cnr = float((q75 - q25) / noise_std)
        else:
            raise NotImplementedError(
                "MRIQualityController: computing SNR/CNR from a bare 'nifti_path' is not "
                "implemented — pass 'voxel_data' in mri_data; synthetic values are not produced"
            )

        qc_flags: list[str] = []
        if snr < float(snr_threshold):
            qc_flags.append("low_snr")
        if mean_fd is not None and mean_fd > float(motion_threshold_mm):
            qc_flags.append("excessive_motion")

        return {
            "snr": snr,
            "cnr": cnr,
            "mean_fd_mm": mean_fd,
            "passes_qc": len(qc_flags) == 0,
            "qc_flags": qc_flags,
        }
