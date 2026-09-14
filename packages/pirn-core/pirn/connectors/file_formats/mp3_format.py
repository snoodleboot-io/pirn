"""``Mp3Format`` — MP3 audio batch encoder/decoder via ``pydub``.

``pydub`` wraps ffmpeg/avconv for actual decode/encode. ffmpeg must be
on ``PATH`` at runtime.

Each file is decoded into ONE record::

    {
        "sample_rate":   int,
        "n_channels":    int,
        "sample_width":  int,   # bytes per sample
        "n_frames":      int,
        "frames":        bytes, # raw PCM frame data
    }

Install: ``pip install "pirn-core[audio]"`` and ensure ffmpeg is installed.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.core.optional_dependency import OptionalDependency


class Mp3Format(BatchFileFormat):
    """Whole-file MP3 encoder/decoder backed by ``pydub``."""

    @property
    def name(self) -> str:
        return "mp3"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not payload:
            raise ValueError("Mp3Format: payload is empty — cannot decode MP3")
        pydub = OptionalDependency.require("pydub", extra="audio")
        segment = pydub.AudioSegment.from_file(io.BytesIO(payload), format="mp3")
        record: dict[str, Any] = {
            "sample_rate": segment.frame_rate,
            "n_channels": segment.channels,
            "sample_width": segment.sample_width,
            "n_frames": int(len(segment.raw_data) / (segment.channels * segment.sample_width)),
            "frames": segment.raw_data,
        }
        return [record]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        materialised = [dict(r) for r in records]
        if not materialised:
            raise ValueError("Mp3Format: cannot encode an empty record stream")
        pydub = OptionalDependency.require("pydub", extra="audio")
        record = materialised[0]
        segment = pydub.AudioSegment(
            data=bytes(record["frames"]),
            sample_width=int(record["sample_width"]),
            frame_rate=int(record["sample_rate"]),
            channels=int(record["n_channels"]),
        )
        buf = io.BytesIO()
        segment.export(buf, format="mp3")
        return buf.getvalue()
