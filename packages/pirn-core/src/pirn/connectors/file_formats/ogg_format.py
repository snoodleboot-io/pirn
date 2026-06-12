"""``OggFormat`` — Ogg Vorbis audio batch encoder/decoder via ``soundfile``.

``soundfile`` (libsndfile binding) supports Ogg Vorbis given a seekable
file-like object or filesystem path. A ``tempfile`` is used for I/O.

Each file is decoded into ONE record::

    {
        "sample_rate":  int,
        "n_channels":   int,
        "n_frames":     int,
        "frames":       bytes,  # raw float32 interleaved PCM bytes
    }

Install: ``pip install pirn[audio]``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class OggFormat(BatchFileFormat):
    """Whole-file Ogg Vorbis encoder/decoder backed by ``soundfile``.

    One record is emitted per file::

        {
            "sample_rate":  int,
            "n_channels":   int,
            "n_frames":     int,
            "frames":       bytes,  # raw float32 interleaved PCM bytes
        }

    Encoding reconstructs the Ogg Vorbis file from the same shape.
    """

    @property
    def name(self) -> str:
        return "ogg"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not payload:
            raise ValueError("OggFormat: payload is empty — cannot decode Ogg")
        sf, _np = self._load_deps()
        with tempfile.NamedTemporaryFile(suffix=".ogg") as tmp:
            tmp.write(payload)
            tmp.flush()
            data, sample_rate = sf.read(tmp.name, dtype="float32", always_2d=True)
        n_frames, n_channels = data.shape
        record: dict[str, Any] = {
            "sample_rate": int(sample_rate),
            "n_channels": int(n_channels),
            "n_frames": int(n_frames),
            "frames": data.tobytes(),
        }
        return [record]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        materialised = [dict(r) for r in records]
        if not materialised:
            raise ValueError("OggFormat: cannot encode an empty record stream")
        sf, np = self._load_deps()
        record = materialised[0]
        n_frames = int(record["n_frames"])
        n_channels = int(record["n_channels"])
        sample_rate = int(record["sample_rate"])
        frames_bytes = bytes(record["frames"])
        data = np.frombuffer(frames_bytes, dtype=np.float32).reshape(n_frames, n_channels)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, data, sample_rate, format="OGG", subtype="VORBIS")
        with open(tmp_path, "rb") as fh:
            payload = fh.read()
        os.unlink(tmp_path)
        return payload

    @staticmethod
    def _load_deps() -> tuple[Any, Any]:
        try:
            import numpy as np
            import soundfile as sf
        except ImportError as exc:
            raise ImportError(
                "OggFormat requires soundfile and numpy. Install with `pip install pirn[audio]`."
            ) from exc
        return sf, np
