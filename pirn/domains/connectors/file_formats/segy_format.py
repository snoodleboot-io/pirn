"""``SegyFormat`` — SEG-Y seismic data batch encoder/decoder.

SEG-Y is the industry-standard format for seismic reflection data. Each
file contains a textual file header, a binary file header, and a sequence
of traces (each with a 240-byte trace header and floating-point sample
data).

Records are emitted as one dict per trace::

    {
        "trace_index": int,
        "header":      dict[str, Any],   # segyio trace header fields
        "data":        bytes,             # raw float32 sample bytes
    }

Install: ``pip install pirn[oilgas]``.
"""

from __future__ import annotations

import struct
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class SegyFormat(BatchFileFormat):
    """Whole-file SEG-Y encoder/decoder backed by ``segyio``.

    Args:
        sample_rate: Sample interval in microseconds used when creating
            new SEG-Y files. Defaults to 2000 (2 ms).
    """

    def __init__(self, sample_rate: int = 2000) -> None:
        if not isinstance(sample_rate, int) or sample_rate <= 0:
            raise ValueError(
                f"SegyFormat: sample_rate must be a positive integer, got {sample_rate!r}"
            )
        self._sample_rate = sample_rate

    @property
    def name(self) -> str:
        return "segy"

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        segyio = self._load_segyio()
        records: list[dict[str, Any]] = []
        with tempfile.NamedTemporaryFile(suffix=".segy", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(payload)
        try:
            with segyio.open(tmp_path, "r", ignore_geometry=True) as f:
                for idx, trace in enumerate(f.trace):
                    header = {}
                    for key in f.header[idx].keys():
                        header[str(key)] = int(f.header[idx][key])
                    data = struct.pack(f">{len(trace)}f", *trace.tolist())
                    records.append(
                        {
                            "trace_index": idx,
                            "header": header,
                            "data": data,
                        }
                    )
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        segyio = self._load_segyio()
        materialised = [dict(r) for r in records]
        if not materialised:
            raise ValueError("SegyFormat: cannot encode an empty record stream")
        import numpy as np

        first_data = materialised[0].get("data", b"")
        if not isinstance(first_data, (bytes, bytearray)):
            raise TypeError(
                f"SegyFormat: record 'data' must be bytes, got {type(first_data).__name__}"
            )
        n_samples = len(first_data) // 4 or 1

        spec = segyio.spec()
        spec.sorting = None
        spec.format = 1  # IBM float
        spec.samples = np.arange(n_samples, dtype=np.float32)
        spec.tracecount = len(materialised)

        with tempfile.NamedTemporaryFile(suffix=".segy", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with segyio.create(tmp_path, spec) as f:
                for idx, record in enumerate(materialised):
                    raw = record.get("data", b"")
                    if not isinstance(raw, (bytes, bytearray)):
                        raw = b"\x00" * (n_samples * 4)
                    n = len(raw) // 4
                    if n == 0:
                        samples = np.zeros(n_samples, dtype=np.float32)
                    else:
                        values = struct.unpack(f">{n}f", raw[: n * 4])
                        samples = np.array(values, dtype=np.float32)
                        if len(samples) < n_samples:
                            samples = np.pad(
                                samples,
                                (0, n_samples - len(samples)),
                            )
                        elif len(samples) > n_samples:
                            samples = samples[:n_samples]
                    f.trace[idx] = samples
                    header = record.get("header", {})
                    if isinstance(header, dict) and header:
                        for key, val in header.items():
                            try:
                                f.header[idx].update({key: int(val)})
                            except (ValueError, TypeError, KeyError):
                                pass
            result = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        return result

    @staticmethod
    def _load_segyio() -> Any:
        try:
            import segyio
        except ImportError as exc:
            raise ImportError(
                "SegyFormat requires segyio. Install with `pip install pirn[oilgas]`."
            ) from exc
        return segyio
