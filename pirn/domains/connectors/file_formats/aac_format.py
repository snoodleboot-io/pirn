"""``AacFormat`` — AAC (ADTS) audio batch encoder/decoder via ``pydub``.

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

Install: ``pip install pirn[audio]`` and ensure ffmpeg is installed.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class AacFormat(BatchFileFormat):
    """Whole-file AAC (ADTS) encoder/decoder backed by ``pydub``."""

    @property
    def name(self) -> str:
        return "aac"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not payload:
            raise ValueError("AacFormat: payload is empty — cannot decode AAC")
        audio_segment_cls = self._load_pydub()
        segment = audio_segment_cls.from_file(io.BytesIO(payload), format="aac")
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
            raise ValueError("AacFormat: cannot encode an empty record stream")
        audio_segment_cls = self._load_pydub()
        record = materialised[0]
        segment = audio_segment_cls(
            data=bytes(record["frames"]),
            sample_width=int(record["sample_width"]),
            frame_rate=int(record["sample_rate"]),
            channels=int(record["n_channels"]),
        )
        buf = io.BytesIO()
        segment.export(buf, format="adts")
        return buf.getvalue()

    @staticmethod
    def _load_pydub() -> Any:
        try:
            from pydub import AudioSegment
        except ImportError as exc:
            raise ImportError(
                "AacFormat requires pydub and ffmpeg. Install with "
                "`pip install pirn[audio]` and ensure ffmpeg is installed."
            ) from exc
        return AudioSegment
