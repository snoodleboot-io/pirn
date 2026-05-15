"""``DicomObjectStoreDisassembler`` — disassemble a :class:`DICOMPayload` into bytes.

Sits between domain knots that produce :class:`~pirn.domains.health.types.dicom_payload.DICOMPayload`
and an object store sink connector that expects raw ``bytes``.

Algorithm:
    1. Receive a :class:`DICOMPayload`.
    2. Validate the payload type.
    3. On a thread, list all ``.dcm`` files in ``payload.dicom_dir`` and read the first one
       via ``pydicom``; raise ``ValueError`` if no files are found.
    4. Return the raw file bytes.

References:
    - pydicom: https://pydicom.github.io/
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pydicom

from pirn.core.disassembler import Disassembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.dicom_payload import DICOMPayload


def _read_first_dcm(payload: DICOMPayload) -> bytes:
    dcm_files = sorted(Path(payload.dicom_dir).glob("*.dcm"))
    if not dcm_files:
        raise ValueError(
            f"DicomObjectStoreDisassembler: no .dcm files found in {payload.dicom_dir!r}"
        )
    ds = pydicom.dcmread(str(dcm_files[0]))
    buf = pydicom.filebase.DicomBytesIO()
    pydicom.dcmwrite(buf, ds)
    return buf.getvalue()


class DicomObjectStoreDisassembler(Disassembler):
    """Disassemble a :class:`DICOMPayload` into raw DICOM bytes for object store upload."""

    def __init__(
        self,
        *,
        payload: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(payload=payload, _config=_config, **kwargs)

    async def process(
        self,
        payload: DICOMPayload,
        **_: Any,
    ) -> bytes:
        """Read the first DICOM file from the payload directory and return its bytes.

        Args:
            payload: :class:`DICOMPayload` carrying the staged DICOM directory path.

        Returns:
            Raw ``bytes`` of the first ``.dcm`` file found in ``payload.dicom_dir``.

        Raises:
            TypeError: If ``payload`` is not a :class:`DICOMPayload`.
            ValueError: If no ``.dcm`` files exist in the staged directory.
        """
        if not isinstance(payload, DICOMPayload):
            raise TypeError(
                f"DicomObjectStoreDisassembler: payload must be DICOMPayload, "
                f"got {type(payload).__name__}"
            )
        return await asyncio.to_thread(_read_first_dcm, payload)
