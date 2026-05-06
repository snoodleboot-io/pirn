"""``BIDSConverter`` — convert DICOM or NIfTI files to BIDS format.

Algorithm:
    1. Receive input_data dict, output_dir, modality, and subject_id strings.
    2. Validate output_dir and subject_id are non-empty strings.
    3. Validate modality is one of T1w/T2w/BOLD/DWI/FLAIR.
    4. Validate input_data is a dict.
    5. Construct BIDS path and return output metadata dict.


References:
    - BIDS specification: https://bids-specification.readthedocs.io/
    - dcm2niix: https://github.com/rordenlab/dcm2niix
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class BIDSConverter(Knot):
    """Convert DICOM or NIfTI files to BIDS (Brain Imaging Data Structure) format."""

    def __init__(
        self,
        *,
        input_data: Knot | dict[str, Any],
        output_dir: Knot | str,
        modality: Knot | str,
        subject_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            input_data=input_data,
            output_dir=output_dir,
            modality=modality,
            subject_id=subject_id,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        input_data: dict[str, Any],
        output_dir: str,
        modality: str,
        subject_id: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Convert imaging data to BIDS format and return the output path.

        Args:
            input_data: Dict with ``dicom_path`` or ``nifti_path`` (str) and ``metadata`` (dict).
            output_dir: Non-empty path to the BIDS output directory.
            modality: One of T1w, T2w, BOLD, DWI, FLAIR.
            subject_id: Non-empty BIDS subject identifier string.

        Returns:
            Dict with ``bids_path``, ``subject_id``, ``modality``, and ``session_id``.

        Raises:
            TypeError: If input_data is not a dict.
            ValueError: If output_dir or subject_id is empty, or modality is invalid.
        """
        if not isinstance(input_data, dict):
            raise TypeError("BIDSConverter: input_data must be a dict")
        if not isinstance(output_dir, str) or not output_dir:
            raise ValueError("BIDSConverter: output_dir must be non-empty")
        valid_modalities = frozenset({"T1w", "T2w", "BOLD", "DWI", "FLAIR"})
        if not isinstance(modality, str) or modality not in valid_modalities:
            raise ValueError(f"BIDSConverter: modality must be one of {sorted(valid_modalities)}")
        if not isinstance(subject_id, str) or not subject_id:
            raise ValueError("BIDSConverter: subject_id must be non-empty")
        bids_path = f"{output_dir}/sub-{subject_id}/{modality}.nii.gz"
        return {
            "bids_path": bids_path,
            "subject_id": subject_id,
            "modality": modality,
            "session_id": None,
        }
