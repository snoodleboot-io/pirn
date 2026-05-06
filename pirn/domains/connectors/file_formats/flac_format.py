"""``FlacFormat`` — FLAC audio batch encoder/decoder via ``soundfile``.

``soundfile`` (libsndfile binding) can read/write FLAC given a seekable
file-like object or a filesystem path. A ``tempfile`` is used for I/O.

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

import tempfile
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class FlacFormat(BatchFileFormat):
    """Whole-file FLAC encoder/decoder backed by ``soundfile``."""

    @property
    def name(self) -> str:
        return "flac"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not payload:
            raise ValueError("FlacFormat: payload is empty — cannot decode FLAC")
        sf, _np = self._load_deps()
        with tempfile.NamedTemporaryFile(suffix=".flac") as tmp:
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
            raise ValueError("FlacFormat: cannot encode an empty record stream")
        sf, np = self._load_deps()
        record = materialised[0]
        n_frames = int(record["n_frames"])
        n_channels = int(record["n_channels"])
        sample_rate = int(record["sample_rate"])
        frames_bytes = bytes(record["frames"])
        data = np.frombuffer(frames_bytes, dtype=np.float32).reshape(n_frames, n_channels)
        with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, data, sample_rate, format="FLAC", subtype="PCM_16")
        with open(tmp_path, "rb") as fh:
            payload = fh.read()
        import os

        os.unlink(tmp_path)
        return payload

    @staticmethod
    def _load_deps() -> tuple[Any, Any]:
        try:
            import numpy as np
            import soundfile as sf
        except ImportError as exc:
            raise ImportError(
                "FlacFormat requires soundfile and numpy. Install with `pip install pirn[audio]`."
            ) from exc
        return sf, np
