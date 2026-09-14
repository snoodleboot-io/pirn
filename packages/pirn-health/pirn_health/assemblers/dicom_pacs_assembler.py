"""``DicomPacsAssembler`` — assemble a :class:`DICOMPayload` from raw DICOM bytes.

Sits between an object store connector (which produces ``bytes``) and downstream
domain knots that consume :class:`~pirn_health.types.dicom_payload.DICOMPayload`.

Algorithm:
    1. Receive ``body`` (raw DICOM bytes) and ``series_id``.
    2. Validate types and values.
    3. Parse ``body`` in memory with ``pydicom.dcmread(io.BytesIO(body))`` on a
       thread — no filesystem I/O; nothing is written to disk.
    4. Return a :class:`DICOMPayload` carrying a :class:`DICOMSeries` metadata stub
       and the parsed ``pydicom.Dataset``.

References:
    - DICOMweb: https://www.dicomstandard.org/dicomweb
    - pydicom: https://pydicom.github.io/
"""

from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime
from typing import Any

from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.dicom_payload import DICOMPayload
from pirn_health.types.dicom_series import DICOMSeries


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
        """Parse DICOM bytes in memory and return a :class:`DICOMPayload`.

        Args:
            body: Raw DICOM file bytes from an object store or PACS connector.
            series_id: Non-empty DICOM series identifier string.

        Returns:
            :class:`DICOMPayload` carrying a :class:`DICOMSeries` metadata stub and
            the parsed ``pydicom.Dataset``.

        Raises:
            TypeError: If ``body`` is not ``bytes`` or ``series_id`` is not a ``str``.
            ValueError: If ``series_id`` is empty.
            ImportError: If ``pydicom`` is not installed.
        """
        if not isinstance(body, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime-bound input; guard is deliberate
            raise TypeError(f"DicomPacsAssembler: body must be bytes, got {type(body).__name__}")
        if not isinstance(series_id, str):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime-bound input; guard is deliberate
            raise TypeError(
                f"DicomPacsAssembler: series_id must be str, got {type(series_id).__name__}"
            )
        if not series_id:
            raise ValueError("DicomPacsAssembler: series_id must be non-empty")
        dataset = await asyncio.to_thread(self._parse_dicom, body)
        series = DICOMSeries(
            series_uid=series_id,
            fetched_at=datetime.now(UTC),
        )
        return DICOMPayload(metadata=series, data=dataset)

    @staticmethod
    def _parse_dicom(body: bytes) -> Any:
        try:
            import pydicom  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "DicomPacsAssembler requires 'pydicom'. Install via `pip install pirn-health[health]`."
            ) from exc
        sdk: Any = pydicom  # optional SDK: lazily imported, used untyped
        return sdk.dcmread(io.BytesIO(body))
