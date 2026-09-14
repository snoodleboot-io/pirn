"""``M4aFormat`` — M4A (AAC in MP4 container) audio batch encoder/decoder.

Uses ``pydub`` (wraps ffmpeg/avconv). ffmpeg must be on ``PATH`` at runtime.

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


class M4aFormat(BatchFileFormat):
    """Whole-file M4A encoder/decoder backed by ``pydub``."""

    @property
    def name(self) -> str:
        return "m4a"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not payload:
            raise ValueError("M4aFormat: payload is empty — cannot decode M4A")
        pydub = OptionalDependency.require("pydub", extra="audio")
        segment = pydub.AudioSegment.from_file(io.BytesIO(payload), format="m4a")
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
            raise ValueError("M4aFormat: cannot encode an empty record stream")
        pydub = OptionalDependency.require("pydub", extra="audio")
        record = materialised[0]
        segment = pydub.AudioSegment(
            data=bytes(record["frames"]),
            sample_width=int(record["sample_width"]),
            frame_rate=int(record["sample_rate"]),
            channels=int(record["n_channels"]),
        )
        buf = io.BytesIO()
        segment.export(buf, format="ipod")
        return buf.getvalue()
