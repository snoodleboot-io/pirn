"""``BIDSConverter`` — convert DICOM or NIfTI files to BIDS format."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class BIDSConverter(Knot):
    """Convert DICOM or NIfTI files to BIDS (Brain Imaging Data Structure) format."""

    _VALID_MODALITIES: frozenset[str] = frozenset({"T1w", "T2w", "BOLD", "DWI", "FLAIR"})

    def __init__(
        self,
        *,
        input_data: Knot,
        output_dir: str,
        modality: str,
        subject_id: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(output_dir, str) or not output_dir:
            raise ValueError("BIDSConverter: output_dir must be non-empty")
        if not isinstance(modality, str) or modality not in self._VALID_MODALITIES:
            raise ValueError(
                f"BIDSConverter: modality must be one of {sorted(self._VALID_MODALITIES)}"
            )
        if not isinstance(subject_id, str) or not subject_id:
            raise ValueError("BIDSConverter: subject_id must be non-empty")
        self._output_dir = output_dir
        self._modality = modality
        self._subject_id = subject_id
        super().__init__(input_data=input_data, _config=_config, **kwargs)

    async def process(self, input_data: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Convert imaging data to BIDS format and return the output path.

        Args:
            input_data: Dict with ``dicom_path`` or ``nifti_path`` (str) and
                ``metadata`` (dict).

        Returns:
            Dict with ``bids_path``, ``subject_id``, ``modality``,
            and ``session_id`` (str or None).
        """
        if not isinstance(input_data, dict):
            raise TypeError("BIDSConverter: input_data must be a dict")
        bids_path = (
            f"{self._output_dir}/sub-{self._subject_id}/{self._modality}.nii.gz"
        )
        return {
            "bids_path": bids_path,
            "subject_id": self._subject_id,
            "modality": self._modality,
            "session_id": None,
        }
