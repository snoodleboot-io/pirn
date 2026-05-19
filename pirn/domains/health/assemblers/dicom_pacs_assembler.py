"""``DicomPacsAssembler`` — assemble a :class:`DICOMPayload` from raw DICOM bytes.

Sits between an object store connector (which produces ``bytes``) and downstream
domain knots that consume :class:`~pirn.domains.health.types.dicom_payload.DICOMPayload`.

Algorithm:
    1. Receive ``body`` (raw DICOM bytes) and ``series_id``.
    2. Validate types and values.
    3. Write the bytes to a temporary directory as ``{series_id}.dcm`` on a thread.
    4. Return a :class:`DICOMPayload` carrying a :class:`DICOMSeries` metadata stub
       and the temporary directory path.

References:
    - DICOMweb: https://www.dicomstandard.org/dicomweb
    - pydicom: https://pydicom.github.io/
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.dicom_payload import DICOMPayload
from pirn.domains.health.types.dicom_series import DICOMSeries


def _write_dicom(body: bytes, series_id: str) -> DICOMPayload:
    temp_dir = tempfile.mkdtemp()
    dest = Path(temp_dir) / f"{series_id}.dcm"
    dest.write_bytes(body)
    series = DICOMSeries(
        series_uid=series_id,
        fetched_at=datetime.now(UTC),
    )
    return DICOMPayload(metadata=series, data=temp_dir)


class DicomPacsAssembler(Assembler):
    """Assemble a :class:`DICOMPayload` from raw DICOM bytes."""

    def __init__(
        self,
        *,
        body: Knot,
        series_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(body=body, series_id=series_id, _config=_config, **kwargs)

    async def process(
        self,
        body: bytes,
        series_id: str,
        **_: Any,
    ) -> DICOMPayload:
        """Write DICOM bytes to a temp directory and return a :class:`DICOMPayload`.

        Args:
            body: Raw DICOM file bytes from an object store or PACS connector.
            series_id: Non-empty DICOM series identifier string.

        Returns:
            :class:`DICOMPayload` carrying a :class:`DICOMSeries` metadata stub and
            the path to the temporary directory where the ``.dcm`` file was written.

        Raises:
            TypeError: If ``body`` is not ``bytes`` or ``series_id`` is not a ``str``.
            ValueError: If ``series_id`` is empty.
        """
        if not isinstance(body, bytes):
            raise TypeError(f"DicomPacsAssembler: body must be bytes, got {type(body).__name__}")
        if not isinstance(series_id, str):
            raise TypeError(
                f"DicomPacsAssembler: series_id must be str, got {type(series_id).__name__}"
            )
        if not series_id:
            raise ValueError("DicomPacsAssembler: series_id must be non-empty")
        return await asyncio.to_thread(_write_dicom, body, series_id)
