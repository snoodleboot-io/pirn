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

Install: ``pip install "pirn-oilgas[oilgas]"``.
"""

from __future__ import annotations

import struct
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.core.optional_dependency import OptionalDependency
from pirn.core.shape_guard import ShapeGuard

if TYPE_CHECKING:
    pass


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
        segyio = OptionalDependency.require("segyio", extra="oilgas", package="pirn-oilgas")
        records: list[dict[str, Any]] = []
        with tempfile.NamedTemporaryFile(suffix=".segy", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(payload)
        try:
            with segyio.open(tmp_path, "r", ignore_geometry=True) as f:
                for idx, trace in enumerate(f.trace):
                    header: dict[str, int] = {}
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
        import numpy as np

        segyio = OptionalDependency.require("segyio", extra="oilgas", package="pirn-oilgas")
        materialised = [dict(r) for r in records]
        if not materialised:
            raise ValueError("SegyFormat: cannot encode an empty record stream")

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
                    f.trace[idx] = self._trace_samples(idx, record, n_samples)
                    updates = self._header_updates(idx, record)
                    if updates:
                        try:
                            f.header[idx].update(updates)
                        except Exception as exc:
                            raise ValueError(
                                f"SegyFormat: trace {idx} header could not be written: {exc}"
                            ) from exc
            result = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        return result

    @staticmethod
    def _trace_samples(trace_index: int, record: Mapping[str, Any], n_samples: int) -> Any:
        """Decode one record's ``data`` into exactly *n_samples* float32 samples.

        SEG-Y fixes the sample count for the whole file, so a trace of a
        different length cannot be written — and must not be made to fit. This
        used to substitute zeros for a non-bytes payload, zero-pad a short trace
        and truncate a long one, all silently, so a ragged record stream wrote a
        file that looked valid and was not the data handed in (PIR-873).

        Args:
            trace_index: The trace's position, for the error messages.
            record: The record being encoded.
            n_samples: Samples per trace, fixed by the first record.

        Returns:
            A ``numpy`` float32 array of exactly *n_samples* samples.

        Raises:
            TypeError: If ``data`` is not bytes.
            ValueError: If ``data`` is not a whole number of big-endian float32
                samples, or does not hold exactly *n_samples* of them.
        """
        import numpy as np

        raw = record.get("data", b"")
        if not isinstance(raw, (bytes, bytearray)):
            raise TypeError(
                f"SegyFormat: trace {trace_index} 'data' must be bytes, got {type(raw).__name__}"
            )
        if len(raw) % 4 != 0:
            raise ValueError(
                f"SegyFormat: trace {trace_index} 'data' is {len(raw)} bytes, which is not a "
                "whole number of 4-byte float32 samples"
            )
        count = len(raw) // 4
        if count != n_samples:
            raise ValueError(
                f"SegyFormat: trace {trace_index} holds {count} samples but the file is being "
                f"written with {n_samples} per trace (set by the first record). SEG-Y traces are "
                "fixed length; pad or trim the records deliberately before encoding."
            )
        values = struct.unpack(f">{count}f", bytes(raw))
        return np.array(values, dtype=np.float32)

    @staticmethod
    def _header_updates(trace_index: int, record: Mapping[str, Any]) -> dict[object, int]:
        """Return the trace-header fields to write, rejecting anything unwritable.

        A SEG-Y trace-header field is an integer. A value that could not be read
        as one, and a ``header`` that was not a mapping at all, used to be
        skipped without a word — so a record carrying a malformed inline number
        wrote a header quietly missing that field (PIR-873).

        Args:
            trace_index: The trace's position, for the error messages.
            record: The record being encoded.

        Returns:
            ``{field: int}`` ready for ``segyio``'s ``header.update``.

        Raises:
            TypeError: If ``header`` is present and not a mapping.
            ValueError: If a header value cannot be read as an integer.
        """
        header = record.get("header")
        if header is None:
            return {}
        if not ShapeGuard.is_mapping(header):
            raise TypeError(
                f"SegyFormat: trace {trace_index} 'header' must be a mapping, "
                f"got {type(header).__name__}"
            )
        updates: dict[object, int] = {}
        for key, val in header.items():
            if not isinstance(val, (int, float, str)):
                raise ValueError(
                    f"SegyFormat: trace {trace_index} header field {key!r} cannot be read as an "
                    f"integer ({type(val).__name__} {val!r}) — SEG-Y trace headers hold integers"
                )
            try:
                updates[key] = int(val)
            except ValueError as exc:
                raise ValueError(
                    f"SegyFormat: trace {trace_index} header field {key!r} cannot be read as an "
                    f"integer ({type(val).__name__} {val!r}) — SEG-Y trace headers hold integers"
                ) from exc
        return updates
