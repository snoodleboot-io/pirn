"""``GribFormat`` — GRIB meteorological data batch decoder (read-only).

GRIB (GRIdded Binary) is the WMO standard format for numerical weather
prediction data. The reference Python binding is ``cfgrib``, which
wraps the ``eccodes`` C library.

Records are emitted as ONE record per GRIB message::

    {
        "shortName":    str,
        "name":         str,
        "typeOfLevel":  str,
        "level":        int | float,
        "stepRange":    str,
        "values":       bytes,    # numpy array of field values as bytes
    }

Encode is not supported because producing GRIB messages requires the
``eccodes`` library's write API, which is outside the scope of this
connector.

Install: ``pip install pirn[weather]``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class GribFormat(BatchFileFormat):
    """Whole-file GRIB decoder backed by ``cfgrib``.

    Decode emits one record per GRIB message. Encode is not supported.
    """

    @property
    def name(self) -> str:
        return "grib"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        cfgrib, eccodes = self._load_cfgrib_eccodes()
        tmp_path = self._write_temp(payload, ".grib2")
        records: list[Mapping[str, Any]] = []
        try:
            with open(tmp_path, "rb") as fh:
                while True:
                    try:
                        msg = eccodes.codes_grib_new_from_file(fh)
                    except Exception:
                        break
                    if msg is None:
                        break
                    try:
                        record = self._extract_message(msg, eccodes)
                        records.append(record)
                    finally:
                        try:
                            eccodes.codes_release(msg)
                        except Exception:
                            pass
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        return records

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        raise NotImplementedError(
            "GribFormat: write is not supported — GRIB encoding requires "
            "eccodes"
        )

    @staticmethod
    def _extract_message(msg: Any, eccodes: Any) -> dict[str, Any]:
        import numpy as np

        def _get(key: str, default: Any = "") -> Any:
            try:
                return eccodes.codes_get(msg, key)
            except Exception:
                return default

        short_name = str(_get("shortName", ""))
        name = str(_get("name", ""))
        type_of_level = str(_get("typeOfLevel", ""))
        level = _get("level", 0)
        step_range = str(_get("stepRange", ""))

        try:
            values = eccodes.codes_get_values(msg)
            values_bytes = np.asarray(values, dtype=np.float64).tobytes()
        except Exception:
            values_bytes = b""

        return {
            "shortName": short_name,
            "name": name,
            "typeOfLevel": type_of_level,
            "level": level,
            "stepRange": step_range,
            "values": values_bytes,
        }

    @staticmethod
    def _write_temp(payload: bytes, suffix: str) -> str:
        tmp_path = tempfile.mktemp(suffix=suffix)
        with open(tmp_path, "wb") as fh:
            fh.write(payload)
        return tmp_path

    @staticmethod
    def _load_cfgrib_eccodes() -> tuple[Any, Any]:
        try:
            import cfgrib
            import eccodes
        except ImportError as exc:
            raise ImportError(
                "GribFormat requires cfgrib and eccodes. Install with "
                "`pip install pirn[weather]`."
            ) from exc
        return cfgrib, eccodes
