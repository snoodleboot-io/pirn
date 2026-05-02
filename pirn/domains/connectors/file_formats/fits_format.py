"""``FitsFormat`` — FITS (Flexible Image Transport System) batch encoder/decoder.

FITS is the standard data format in astronomy, used to store images,
spectra, and tabular data. Each FITS file is composed of Header/Data
Units (HDUs). The reference Python binding is ``astropy.io.fits``.

Records are emitted as ONE record per HDU with shape::

    {
        "hdu_index": int,
        "hdu_type":  str,
        "header":    dict[str, Any],
        "data":      bytes | None,
    }

where ``data`` is ``hdu.data.tobytes()`` if the HDU has data, else
``None``.

Install: ``pip install pirn[astronomy]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class FitsFormat(BatchFileFormat):
    """Whole-file FITS encoder/decoder backed by ``astropy.io.fits``.

    Decode emits one record per HDU. Encode reconstructs a minimal FITS
    file from the records, writing a primary HDU from the first record.
    """

    @property
    def name(self) -> str:
        return "fits"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        fits = self._load_fits()
        records: list[Mapping[str, Any]] = []
        with fits.open(io.BytesIO(payload)) as hdul:
            for index, hdu in enumerate(hdul):
                header: dict[str, Any] = {}
                for card in hdu.header.cards:
                    key = card.keyword
                    if key:
                        header[key] = card.value
                data_bytes: bytes | None = None
                if hdu.data is not None:
                    try:
                        data_bytes = hdu.data.tobytes()
                    except Exception:
                        data_bytes = None
                records.append(
                    {
                        "hdu_index": index,
                        "hdu_type": type(hdu).__name__,
                        "header": header,
                        "data": data_bytes,
                    }
                )
        return records

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        fits = self._load_fits()
        materialised = [dict(record) for record in records]
        hdul = fits.HDUList()
        for i, record in enumerate(materialised):
            header_dict = record.get("header") or {}
            data_bytes = record.get("data")
            hdu_header = fits.Header()
            for key, value in header_dict.items():
                if isinstance(key, str) and key not in (
                    "SIMPLE",
                    "EXTEND",
                    "END",
                    "XTENSION",
                ):
                    try:
                        hdu_header[key] = value
                    except Exception:
                        pass
            if data_bytes is not None and isinstance(data_bytes, (bytes, bytearray)):
                import numpy as np

                arr = np.frombuffer(data_bytes, dtype=np.uint8)
                if i == 0:
                    hdu = fits.PrimaryHDU(data=arr, header=hdu_header)
                else:
                    hdu = fits.ImageHDU(data=arr, header=hdu_header)
            else:
                if i == 0:
                    hdu = fits.PrimaryHDU(header=hdu_header)
                else:
                    hdu = fits.ImageHDU(header=hdu_header)
            hdul.append(hdu)
        if not hdul:
            hdul.append(fits.PrimaryHDU())
        buf = io.BytesIO()
        hdul.writeto(buf, overwrite=True)
        return buf.getvalue()

    @staticmethod
    def _load_fits() -> Any:
        try:
            from astropy.io import fits
        except ImportError as exc:
            raise ImportError(
                "FitsFormat requires astropy. Install with "
                "`pip install pirn[astronomy]`."
            ) from exc
        return fits
