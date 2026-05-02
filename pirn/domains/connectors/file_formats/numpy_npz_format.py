"""``NumpyNpzFormat`` — NumPy zip-of-arrays ``.npz`` batch encoder/decoder.

The ``.npz`` format is a zip archive of one or more named ``.npy``
arrays. ``numpy.load`` requires the whole payload before it can index
the archive, so this is a :class:`BatchFileFormat`.

This implementation stores records as a single named structured-array
entry (default name ``"records"``); decoding looks up that entry and
yields row dicts.

Install: ``pip install pirn[ml]`` (numpy lives in the ``ml`` extra).
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class NumpyNpzFormat(BatchFileFormat):
    """Whole-file ``.npz`` encoder/decoder backed by ``numpy``.

    Args:
        array_name: Name of the structured-array entry inside the
            ``.npz`` archive. Must be a non-empty string.
        field_names: Optional ordered tuple of column names. Used as
            the field order at encode time when supplied; ignored at
            decode time (the stored array is always structured).
    """

    def __init__(
        self,
        array_name: str = "records",
        field_names: Sequence[str] | None = None,
    ) -> None:
        if not isinstance(array_name, str) or not array_name:
            raise ValueError(
                "NumpyNpzFormat: array_name must be a non-empty string"
            )
        if field_names is not None:
            if not isinstance(field_names, Sequence) or isinstance(
                field_names, (str, bytes)
            ):
                raise TypeError(
                    "NumpyNpzFormat: field_names must be a sequence "
                    f"of strings, got {type(field_names).__name__}"
                )
            for name in field_names:
                if not isinstance(name, str) or not name:
                    raise ValueError(
                        "NumpyNpzFormat: every field name must be a "
                        f"non-empty string, got {name!r}"
                    )
        self._array_name = array_name
        self._field_names: tuple[str, ...] | None = (
            tuple(field_names) if field_names is not None else None
        )

    @property
    def name(self) -> str:
        return "numpy-npz"

    @property
    def array_name(self) -> str:
        return self._array_name

    @property
    def field_names(self) -> tuple[str, ...] | None:
        return self._field_names

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        np = self._load_numpy()
        with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
            if self._array_name not in archive.files:
                raise ValueError(
                    "NumpyNpzFormat: archive does not contain "
                    f"{self._array_name!r}; available: {archive.files}"
                )
            array = archive[self._array_name]
            if array.dtype.names is None:
                raise ValueError(
                    "NumpyNpzFormat: stored array is not structured; "
                    "cannot reconstruct records"
                )
            records: list[Mapping[str, Any]] = []
            for row in array:
                record: dict[str, Any] = {}
                for field in array.dtype.names:
                    record[field] = self._unwrap_scalar(row[field], np)
                records.append(record)
        return records

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        np = self._load_numpy()
        materialised = [dict(record) for record in records]
        if not materialised:
            raise ValueError(
                "NumpyNpzFormat: cannot encode an empty record stream "
                "(.npz requires a structured array with at least one "
                "row)"
            )
        structured = self._records_to_structured_array(materialised, np)
        buf = io.BytesIO()
        np.savez(buf, **{self._array_name: structured})
        return buf.getvalue()

    def _records_to_structured_array(
        self, records: list[dict[str, Any]], np: Any
    ) -> Any:
        field_order = self._derive_field_order(records)
        dtype_fields: list[tuple[str, Any]] = []
        for field in field_order:
            sample_value = next(
                (rec[field] for rec in records if field in rec), None
            )
            dtype_fields.append(
                (field, self._infer_numpy_dtype(sample_value, records, field, np))
            )
        structured = np.zeros(len(records), dtype=dtype_fields)
        for index, record in enumerate(records):
            for field in field_order:
                if field in record:
                    structured[index][field] = record[field]
                else:
                    structured[index][field] = self._zero_for_dtype(
                        structured.dtype.fields[field][0]
                    )
        return structured

    def _derive_field_order(
        self, records: list[dict[str, Any]]
    ) -> list[str]:
        if self._field_names is not None:
            return list(self._field_names)
        order: list[str] = []
        seen: set[str] = set()
        for record in records:
            for key in record.keys():
                if key not in seen:
                    seen.add(key)
                    order.append(key)
        return order

    @staticmethod
    def _infer_numpy_dtype(
        sample_value: Any,
        records: list[dict[str, Any]],
        field: str,
        np: Any,
    ) -> Any:
        if isinstance(sample_value, bool):
            return np.bool_
        if isinstance(sample_value, int):
            return np.int64
        if isinstance(sample_value, float):
            return np.float64
        if isinstance(sample_value, str):
            max_len = max(
                (
                    len(rec[field])
                    for rec in records
                    if isinstance(rec.get(field), str)
                ),
                default=1,
            )
            return f"U{max(max_len, 1)}"
        if isinstance(sample_value, bytes):
            max_len = max(
                (
                    len(rec[field])
                    for rec in records
                    if isinstance(rec.get(field), bytes)
                ),
                default=1,
            )
            return f"S{max(max_len, 1)}"
        return np.float64

    @staticmethod
    def _zero_for_dtype(dtype: Any) -> Any:
        kind = dtype.kind
        if kind in ("U", "S"):
            return ""
        if kind == "b":
            return False
        if kind in ("i", "u"):
            return 0
        if kind == "f":
            return 0.0
        return 0

    @staticmethod
    def _unwrap_scalar(value: Any, np: Any) -> Any:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        if isinstance(value, np.ndarray) and value.shape == ():
            return NumpyNpzFormat._unwrap_scalar(value.item(), np)
        if hasattr(value, "item"):
            return value.item()
        return value

    @staticmethod
    def _load_numpy() -> Any:
        try:
            import numpy as np
        except ImportError as exc:
            raise ImportError(
                "NumpyNpzFormat requires numpy. Install with "
                "`pip install pirn[ml]`."
            ) from exc
        return np
