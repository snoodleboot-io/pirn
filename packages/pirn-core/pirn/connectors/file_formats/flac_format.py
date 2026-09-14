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

Install: ``pip install "pirn-core[audio]"``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.core.optional_dependency import OptionalDependency

if TYPE_CHECKING:
    pass


class FlacFormat(BatchFileFormat):
    """Whole-file FLAC encoder/decoder backed by ``soundfile``.

    One record is emitted per file::

        {
            "sample_rate":  int,
            "n_channels":   int,
            "n_frames":     int,
            "frames":       bytes,  # raw float32 interleaved PCM bytes
        }

    Encoding reconstructs the FLAC file from the same shape.
    """

    @property
    def name(self) -> str:
        return "flac"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not payload:
            raise ValueError("FlacFormat: payload is empty — cannot decode FLAC")
        sf = OptionalDependency.require("soundfile", extra="audio")
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
        import numpy as np

        materialised = [dict(r) for r in records]
        if not materialised:
            raise ValueError("FlacFormat: cannot encode an empty record stream")
        sf = OptionalDependency.require("soundfile", extra="audio")
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
        os.unlink(tmp_path)
        return payload
