"""``DicomObjectStoreDisassembler`` — disassemble a :class:`DICOMPayload` into bytes.

Sits between domain knots that produce :class:`~pirn_health.types.dicom_payload.DICOMPayload`
and an object store sink connector that expects raw ``bytes``.

Algorithm:
    1. Receive a :class:`DICOMPayload`.
    2. Validate the payload type.
    3. On a thread, serialise ``payload.data`` with
       ``dataset.save_as(BytesIO())`` — no filesystem I/O.
    4. Return the resulting ``bytes``.

References:
    - pydicom: https://pydicom.github.io/
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

from pirn.core.disassembler import Disassembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.dicom_payload import DICOMPayload


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
        """Serialise the payload's parsed dataset back to DICOM bytes.

        Args:
            payload: :class:`DICOMPayload` carrying the parsed ``pydicom.Dataset``.

        Returns:
            Raw ``bytes`` of the DICOM-encoded dataset.

        Raises:
            TypeError: If ``payload`` is not a :class:`DICOMPayload`, or its
                dataset does not support ``save_as`` (e.g. ``pydicom`` was never
                available to parse it in the first place).
        """
        if not isinstance(payload, DICOMPayload):
            raise TypeError(
                f"DicomObjectStoreDisassembler: payload must be DICOMPayload, "
                f"got {type(payload).__name__}"
            )
        dataset = payload.data
        if not hasattr(dataset, "save_as"):
            raise TypeError(
                "DicomObjectStoreDisassembler: payload.data must be a pydicom Dataset "
                f"(support save_as), got {type(dataset).__name__}"
            )
        return await asyncio.to_thread(self._serialise, dataset)

    @staticmethod
    def _serialise(dataset: Any) -> bytes:
        buf = io.BytesIO()
        dataset.save_as(buf)
        return buf.getvalue()
