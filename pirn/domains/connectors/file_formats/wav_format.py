"""``WavFormat`` — WAV (Waveform Audio File Format) batch encoder/decoder.

Uses the stdlib ``wave`` module only; no optional dependencies required.

Each file is decoded into ONE record::

    {
        "sample_rate":  int,
        "n_channels":   int,
        "sampwidth":    int,   # bytes per sample
        "n_frames":     int,
        "frames":       bytes, # raw PCM frame data
    }

Encoding reconstructs the WAV file from the same shape.
"""

from __future__ import annotations

import io
import wave
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class WavFormat(BatchFileFormat):
    """Whole-file WAV encoder/decoder backed by stdlib ``wave``.

    One record is emitted per file::

        {
            "sample_rate":  int,
            "n_channels":   int,
            "sampwidth":    int,    # bytes per sample
            "n_frames":     int,
            "frames":       bytes,  # raw interleaved PCM frame data
        }

    Encoding reconstructs the WAV file from the same shape.
    """

    @property
    def name(self) -> str:
        return "wav"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not payload:
            raise ValueError("WavFormat: payload is empty — cannot decode WAV")
        buf = io.BytesIO(payload)
        with wave.open(buf, "rb") as wf:
            record: dict[str, Any] = {
                "sample_rate": wf.getframerate(),
                "n_channels": wf.getnchannels(),
                "sampwidth": wf.getsampwidth(),
                "n_frames": wf.getnframes(),
                "frames": wf.readframes(wf.getnframes()),
            }
        return [record]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        materialised = [dict(r) for r in records]
        if not materialised:
            raise ValueError("WavFormat: cannot encode an empty record stream")
        record = materialised[0]
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(int(record["n_channels"]))
            wf.setsampwidth(int(record["sampwidth"]))
            wf.setframerate(int(record["sample_rate"]))
            wf.writeframes(bytes(record["frames"]))
        return buf.getvalue()
