# pyright: reportUnnecessaryIsInstance=false
# runtime-bound inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``NumpyNpyFormat`` — NumPy single-array ``.npy`` batch encoder/decoder.

The ``.npy`` format stores a single ndarray with header-encoded dtype
metadata. ``numpy.load`` requires a seekable file (or :class:`io.BytesIO`)
and reads the entire payload, so this is a :class:`BatchFileFormat`.

Records are serialised as one numpy *structured array* — each record
becomes a row, each dict key becomes a named field. Reads accept a
structured array (returning row dicts) or, when ``field_names`` is
supplied, a 2-D ndarray paired column-wise to the supplied names.

numpy is a core dependency of ``pirn-core``; no extra is required.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.payload_shape import PayloadShape

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt


class NumpyNpyFormat(BatchFileFormat):
    """Whole-file ``.npy`` encoder/decoder backed by ``numpy``.

    Args:
        field_names: Optional ordered tuple of column names. Required
            when reading non-structured 2-D arrays so that columns can
            be paired with record keys; ignored when the stored array
            is already structured. When encoding, if supplied it
            overrides the default (record-key-derived) field order.
    """

    def __init__(
        self,
        field_names: Sequence[str] | None = None,
    ) -> None:
        if field_names is not None:
            if not isinstance(field_names, Sequence) or isinstance(field_names, (str, bytes)):
                raise TypeError(
                    "NumpyNpyFormat: field_names must be a sequence "
                    f"of strings, got {type(field_names).__name__}"
                )
            for name in field_names:
                if not isinstance(name, str) or not name:
                    raise ValueError(
                        f"NumpyNpyFormat: every field name must be a non-empty string, got {name!r}"
                    )
        self._field_names: tuple[str, ...] | None = (
            tuple(field_names) if field_names is not None else None
        )

    @property
    def name(self) -> str:
        return "numpy-npy"

    @property
    def field_names(self) -> tuple[str, ...] | None:
        return self._field_names

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        import numpy as np

        array = np.load(io.BytesIO(payload), allow_pickle=False)
        if array.dtype.names is not None:
            return self._iter_structured(array)
        if self._field_names is None:
            raise ValueError(
                "NumpyNpyFormat: stored array is not structured and "
                "field_names was not provided; cannot reconstruct "
                "records"
            )
        if array.ndim != 2:
            raise ValueError(
                "NumpyNpyFormat: non-structured array must be 2-D "
                f"when field_names is given, got {array.ndim}-D"
            )
        if array.shape[1] != len(self._field_names):
            raise ValueError(
                "NumpyNpyFormat: column count "
                f"{array.shape[1]} does not match field_names length "
                f"{len(self._field_names)}"
            )
        records: list[Mapping[str, Any]] = []
        for row in array:
            record = {
                name: self._unwrap_scalar(row[index])
                for index, name in enumerate(self._field_names)
            }
            records.append(record)
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        import numpy as np

        materialised = [dict(record) for record in records]
        if not materialised:
            raise ValueError(
                "NumpyNpyFormat: cannot encode an empty record stream "
                "(.npy requires a structured array with at least one "
                "row)"
            )
        structured = self._records_to_structured_array(materialised)
        buf = io.BytesIO()
        np.save(buf, structured, allow_pickle=False)
        return buf.getvalue()

    @classmethod
    def _records_to_structured_array(cls, records: list[dict[str, Any]]) -> npt.NDArray[np.void]:
        import numpy as np

        field_order = cls._derive_field_order(records)
        dtype_fields: list[tuple[str, type[np.generic] | str]] = []
        for field in field_order:
            sample_value = next((rec[field] for rec in records if field in rec), None)
            dtype_fields.append((field, cls._infer_numpy_dtype(sample_value, records, field)))
        zero_values = {field: cls._zero_for_dtype(np.dtype(spec)) for field, spec in dtype_fields}
        structured = np.zeros(len(records), dtype=dtype_fields)
        for index, record in enumerate(records):
            for field in field_order:
                if field in record:
                    structured[index][field] = record[field]
                else:
                    structured[index][field] = zero_values[field]
        return structured

    @staticmethod
    def _derive_field_order(records: list[dict[str, Any]]) -> list[str]:
        field_order: list[str] = []
        seen: set[str] = set()
        for record in records:
            for key in record.keys():
                if key not in seen:
                    seen.add(key)
                    field_order.append(key)
        return field_order

    @staticmethod
    def _iter_structured(array: Any) -> list[Mapping[str, Any]]:
        records: list[Mapping[str, Any]] = []
        names = array.dtype.names
        for row in array:
            record: dict[str, Any] = {}
            for field in names:
                record[field] = NumpyNpyFormat._unwrap_scalar(row[field])
            records.append(record)
        return records

    @staticmethod
    def _infer_numpy_dtype(
        sample_value: object,
        records: list[dict[str, Any]],
        field: str,
    ) -> type[np.generic] | str:
        import numpy as np

        if isinstance(sample_value, bool):
            return np.bool_
        if isinstance(sample_value, int):
            return np.int64
        if isinstance(sample_value, float):
            return np.float64
        if isinstance(sample_value, str):
            max_len = max(
                (len(rec[field]) for rec in records if isinstance(rec.get(field), str)),
                default=1,
            )
            return f"U{max(max_len, 1)}"
        if isinstance(sample_value, bytes):
            max_len = max(
                (len(rec[field]) for rec in records if isinstance(rec.get(field), bytes)),
                default=1,
            )
            return f"S{max(max_len, 1)}"
        return np.float64

    @staticmethod
    def _zero_for_dtype(dtype: np.dtype[Any]) -> str | bool | int | float:
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

    @classmethod
    def _unwrap_scalar(cls, value: Any) -> Any:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        if PayloadShape.is_ndarray(value):
            array = value
            if array.shape == ():
                return cls._unwrap_scalar(array.item())
            return array.item()
        if hasattr(value, "item"):
            return value.item()
        return value
