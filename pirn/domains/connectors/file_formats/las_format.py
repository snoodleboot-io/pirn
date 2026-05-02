"""``LasFormat`` — LAS (Log ASCII Standard) well log batch encoder/decoder.

LAS is a widely used ASCII/binary format for borehole well log data. Each
file contains curve definitions, header metadata, and depth-indexed data
columns.

A single record is emitted per file::

    {
        "curves":   list[str],          # curve names in order
        "data":     list[list[float]],  # rows; each row = one depth sample
        "metadata": dict,               # file-level header info
    }

Install: ``pip install pirn[oilgas]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class LasFormat(BatchFileFormat):
    """Whole-file LAS encoder/decoder backed by ``lasio``."""

    @property
    def name(self) -> str:
        return "las"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        lasio = self._load_lasio()
        text = payload.decode("utf-8", errors="replace")
        las = lasio.read(io.StringIO(text))
        curves = list(las.keys())
        data: list[list[float]] = []
        n_rows = len(las[curves[0]]) if curves else 0
        for row_idx in range(n_rows):
            row = [float(las[curve][row_idx]) for curve in curves]
            data.append(row)
        metadata: dict[str, Any] = {}
        for section_name in ("well", "params", "curves", "other"):
            section = getattr(las, section_name, None)
            if section is None:
                continue
            if hasattr(section, "items"):
                for key, item in section.items():
                    metadata[f"{section_name}.{key}"] = getattr(
                        item, "value", str(item)
                    )
        record: dict[str, Any] = {
            "curves": curves,
            "data": data,
            "metadata": metadata,
        }
        return [record]

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        lasio = self._load_lasio()
        materialised = [dict(r) for r in records]
        if not materialised:
            raise ValueError(
                "LasFormat: cannot encode an empty record stream"
            )
        record = materialised[0]
        curves: list[str] = list(record.get("curves", []))
        data: list[list[float]] = list(record.get("data", []))
        import numpy as np

        las = lasio.LASFile()
        if not curves:
            buf = io.StringIO()
            las.write(buf)
            return buf.getvalue().encode("utf-8")
        depth_curve = curves[0]
        depth_values = (
            [row[0] for row in data] if data else []
        )
        las.add_curve(
            depth_curve,
            np.array(depth_values, dtype=float),
            unit="m",
        )
        for col_idx, curve_name in enumerate(curves[1:], start=1):
            values = [row[col_idx] for row in data] if data else []
            las.add_curve(
                curve_name,
                np.array(values, dtype=float),
            )
        buf = io.StringIO()
        las.write(buf)
        return buf.getvalue().encode("utf-8")

    @staticmethod
    def _load_lasio() -> Any:
        try:
            import lasio
        except ImportError as exc:
            raise ImportError(
                "LasFormat requires lasio. Install with "
                "`pip install pirn[oilgas]`."
            ) from exc
        return lasio
