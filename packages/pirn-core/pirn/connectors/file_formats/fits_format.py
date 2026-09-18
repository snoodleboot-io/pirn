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

Install: ``pip install "pirn-core[fits]"``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.core.optional_dependency import OptionalDependency
from pirn.core.shape_guard import ShapeGuard

if TYPE_CHECKING:
    pass


class FitsFormat(BatchFileFormat):
    """Whole-file FITS encoder/decoder backed by ``astropy.io.fits``.

    Decode emits one record per HDU. Encode reconstructs a minimal FITS
    file from the records, writing a primary HDU from the first record.
    """

    @property
    def name(self) -> str:
        return "fits"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        fits = OptionalDependency.require("astropy.io.fits", extra="fits")
        records: list[Mapping[str, Any]] = []
        with fits.open(io.BytesIO(payload)) as hdul:
            for index, hdu in enumerate(hdul):
                header: dict[str, Any] = {}
                for card in hdu.header.cards:
                    key = card.keyword
                    if key:
                        header[key] = card.value
                data_bytes = self._hdu_data_bytes(index, hdu)
                records.append(
                    {
                        "hdu_index": index,
                        "hdu_type": type(hdu).__name__,
                        "header": header,
                        "data": data_bytes,
                    }
                )
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        import numpy as np

        fits = OptionalDependency.require("astropy.io.fits", extra="fits")
        materialised = [dict(record) for record in records]
        hdul = fits.HDUList()
        for i, record in enumerate(materialised):
            header_dict: object = record.get("header") or {}
            if not ShapeGuard.is_mapping(header_dict):
                raise TypeError(
                    f"FitsFormat: record 'header' must be a mapping, got {type(header_dict).__name__}"
                )
            data_bytes = record.get("data")
            hdu_header = fits.Header()
            for key, value in self._writable_header_cards(i, header_dict):
                try:
                    hdu_header[key] = value
                except (ValueError, KeyError, TypeError) as exc:
                    raise ValueError(
                        f"FitsFormat: record {i} header card {key!r} cannot be written to a "
                        f"FITS header: {exc}"
                    ) from exc
            if data_bytes is not None and isinstance(data_bytes, (bytes, bytearray)):
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
    def _hdu_data_bytes(index: int, hdu: Any) -> bytes | None:
        """Return an HDU's data as bytes, or ``None`` when it genuinely has none.

        An HDU whose data cannot be serialised raises rather than yielding
        ``None``: ``None`` already means "this HDU has no data", so returning it
        for a failure made a dropped array indistinguishable from an empty one,
        and the record round-tripped back out with the data missing (PIR-873).

        Args:
            index: The HDU's position in the file, for the error message.
            hdu: The ``astropy.io.fits`` HDU.

        Returns:
            ``hdu.data.tobytes()``, or ``None`` if the HDU carries no data.

        Raises:
            ValueError: If the HDU has data that cannot be serialised.
        """
        if hdu.data is None:
            return None
        try:
            payload: bytes = hdu.data.tobytes()
        except (AttributeError, ValueError, MemoryError, TypeError) as exc:
            raise ValueError(
                f"FitsFormat: HDU {index} has data that cannot be read as bytes: {exc}"
            ) from exc
        return payload

    @staticmethod
    def _writable_header_cards(index: int, header: Mapping[Any, Any]) -> list[tuple[str, Any]]:
        """Return the header cards to write, rejecting anything that is not a card.

        The structural keywords (``SIMPLE``, ``EXTEND``, ``END``, ``XTENSION``)
        are skipped deliberately: ``astropy`` writes them itself from the HDU
        type, and a record carrying them back in would fight that. Every other
        key must be a string, because a FITS keyword is one — a non-string key
        used to be dropped without a word (PIR-873).

        Args:
            index: The record's position, for the error message.
            header: The record's ``header`` mapping.

        Returns:
            ``(keyword, value)`` pairs in the mapping's order.

        Raises:
            TypeError: If a key is not a string.
        """
        structural = ("SIMPLE", "EXTEND", "END", "XTENSION")
        cards: list[tuple[str, Any]] = []
        for key, value in header.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"FitsFormat: record {index} header key must be str, "
                    f"got {type(key).__name__} ({key!r})"
                )
            if key not in structural:
                cards.append((key, value))
        return cards
