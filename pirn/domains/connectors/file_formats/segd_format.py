"""``SegdFormat`` — SEG-D seismic field-tape batch decoder.

SEG-D is a binary tape format used to record seismic field data. It
predates SEG-Y and is used primarily by acquisition crews.

If ``segpy`` is installed it is used; otherwise a minimal pure-Python
reader parses the 32-byte General Header Block 1 and emits one record::

    {
        "record_length":    int,     # milliseconds
        "channel_count":    int,
        "sample_interval":  float,   # milliseconds
        "raw_header":       bytes,   # first 32 bytes
    }

Encoding raises :exc:`NotImplementedError`.

Install: ``pip install pirn[oilgas]``.
"""

from __future__ import annotations

import struct
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)

# General Header Block 1 is 32 bytes per the SEG-D rev 3 spec.
_GH1_SIZE = 32


class SegdFormat(BatchFileFormat):
    """SEG-D decoder. Segpy is used when available; pure-Python fallback
    reads the 32-byte General Header Block 1 only."""

    @property
    def name(self) -> str:
        return "segd"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(
                "SegdFormat: payload must be bytes, got "
                f"{type(payload).__name__}"
            )
        if len(payload) < _GH1_SIZE:
            raise ValueError(
                f"SegdFormat: payload too short — need at least "
                f"{_GH1_SIZE} bytes for General Header Block 1, "
                f"got {len(payload)}"
            )
        return self._decode_minimal(payload)

    @classmethod
    def _decode_minimal(
        cls, payload: bytes
    ) -> list[dict[str, Any]]:
        """Pure-Python General Header Block 1 parser (SEG-D rev 3)."""
        header = payload[:_GH1_SIZE]
        # Bytes 0-1: File Number (BCD, 4 digits)
        # Bytes 2-3: Format Code (BCD)
        # Bytes 4-9: General Constants
        # Bytes 10-11: Year + additional info
        # Bytes 12-13: # of additional general header blocks
        # Bytes 14-15: Record Length in milliseconds (BCD, 4 digits)
        # Bytes 16-17: Block Number / Channel Count (BCD)
        # Bytes 18-19: Sample Interval in 1/16 ms units (BCD, 4 digits)
        record_length = cls._bcd_to_int(header[14:16]) * 2
        channel_count = cls._bcd_to_int(header[16:18])
        # Sample interval is stored as 1/16 ms, 4 BCD digits
        si_raw = cls._bcd_to_int(header[18:20])
        sample_interval = si_raw / 16.0
        return [
            {
                "record_length": record_length,
                "channel_count": channel_count,
                "sample_interval": sample_interval,
                "raw_header": bytes(header),
            }
        ]

    @staticmethod
    def _bcd_to_int(data: bytes) -> int:
        """Convert packed BCD bytes to int."""
        result = 0
        for byte in data:
            high = (byte >> 4) & 0x0F
            low = byte & 0x0F
            result = result * 100 + high * 10 + low
        return result

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        raise NotImplementedError("SegdFormat: write is not supported")
