"""``DlisFormat`` — DLIS (Digital Log Interchange Standard) batch decoder.

DLIS is a complex binary well log format used in the oil & gas industry.
It organises data into logical files, frames, and channels. Writing DLIS
is not supported; use an upstream tool such as ``dlisio`` directly.

Records are emitted as one dict per channel per frame::

    {
        "frame_name":   str,
        "channel_name": str,
        "data":         bytes,  # raw bytes of the channel numpy array
    }

Encoding raises :exc:`NotImplementedError`.

Install: ``pip install pirn[oilgas]``.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class DlisFormat(BatchFileFormat):
    """DLIS decoder backed by ``dlisio``. Encoding is not supported."""

    @property
    def name(self) -> str:
        return "dlis"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        dlisio = self._load_dlisio()
        records: list[dict[str, Any]] = []
        with tempfile.NamedTemporaryFile(
            suffix=".dlis", delete=False
        ) as tmp:
            tmp_path = tmp.name
            tmp.write(payload)
        try:
            with dlisio.dlis(tmp_path) as files:
                for logical_file in files:
                    for frame in logical_file.frames:
                        frame_name = str(
                            getattr(frame, "name", "unknown")
                        )
                        for channel in frame.channels:
                            channel_name = str(
                                getattr(channel, "name", "unknown")
                            )
                            try:
                                array = channel.curves()
                                data = array.tobytes()
                            except Exception:
                                data = b""
                            records.append(
                                {
                                    "frame_name": frame_name,
                                    "channel_name": channel_name,
                                    "data": data,
                                }
                            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        return records

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        raise NotImplementedError("DlisFormat: write is not supported")

    @staticmethod
    def _load_dlisio() -> Any:
        try:
            import dlisio
        except ImportError as exc:
            raise ImportError(
                "DlisFormat requires dlisio. Install with "
                "`pip install pirn[oilgas]`."
            ) from exc
        return dlisio
