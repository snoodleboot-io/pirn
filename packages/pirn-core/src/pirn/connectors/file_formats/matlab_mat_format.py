"""``MatlabMatFormat`` — MATLAB ``.mat`` batch encoder/decoder.

Uses ``scipy.io.loadmat`` / ``scipy.io.savemat`` (MAT-file v5; v7.3 is
HDF5-based and requires ``h5py`` — out of scope for this format). MAT
files store named variables: this implementation persists records as a
single named structured array (default name ``"data"``) of length N.

``scipy.io`` represents structured rows as ``(1, N)`` object-array
matrices on the way out; the decode path unwraps those wrappers back
into Python primitives so round-trips return ``dict`` rows.

Install: ``pip install pirn[matlab]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class MatlabMatFormat(BatchFileFormat):
    """Whole-file ``.mat`` encoder/decoder backed by ``scipy.io``.

    Args:
        variable_name: MATLAB variable name under which the structured
            array is stored. Must satisfy MATLAB's identifier rules
            (alphanumeric + underscore, leading letter); we enforce
            non-empty string here and let scipy reject malformed names.
        field_names: Optional ordered tuple of column names. Used as
            field order at encode time when supplied.
    """

    def __init__(
        self,
        variable_name: str = "data",
        field_names: Sequence[str] | None = None,
    ) -> None:
        if not isinstance(variable_name, str) or not variable_name:
            raise ValueError("MatlabMatFormat: variable_name must be a non-empty string")
        if field_names is not None:
            if not isinstance(field_names, Sequence) or isinstance(field_names, (str, bytes)):
                raise TypeError(
                    "MatlabMatFormat: field_names must be a sequence "
                    f"of strings, got {type(field_names).__name__}"
                )
            for name in field_names:
                if not isinstance(name, str) or not name:
                    raise ValueError(
                        "MatlabMatFormat: every field name must be a "
                        f"non-empty string, got {name!r}"
                    )
        self._variable_name = variable_name
        self._field_names: tuple[str, ...] | None = (
            tuple(field_names) if field_names is not None else None
        )

    @property
    def name(self) -> str:
        return "matlab-mat"

    @property
    def variable_name(self) -> str:
        return self._variable_name

    @property
    def field_names(self) -> tuple[str, ...] | None:
        return self._field_names

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        scipy_io, np = self._load_scipy_numpy()
        # scipy.io.loadmat may invoke pickle for MATLAB object arrays (cell
        # arrays containing arbitrary MATLAB objects). Do not load untrusted
        # .mat files without additional validation at the call site.
        loaded = scipy_io.loadmat(io.BytesIO(payload))
        if self._variable_name not in loaded:
            raise ValueError(
                "MatlabMatFormat: variable "
                f"{self._variable_name!r} not found in .mat file; "
                "available: "
                f"{[k for k in loaded if not k.startswith('__')]}"
            )
        array = loaded[self._variable_name]
        if array.dtype.names is None:
            raise ValueError(
                f"MatlabMatFormat: variable {self._variable_name!r} is not a structured array"
            )
        # scipy.io packs the record array as shape (1, N).
        if array.ndim == 2 and array.shape[0] == 1:
            row_iter = array[0]
        else:
            row_iter = array
        records: list[Mapping[str, Any]] = []
        for row in row_iter:
            record: dict[str, Any] = {}
            for field in array.dtype.names:
                record[field] = self._unwrap_matlab_scalar(row[field], np)
            records.append(record)
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        scipy_io, np = self._load_scipy_numpy()
        materialised = [dict(record) for record in records]
        if not materialised:
            raise ValueError(
                "MatlabMatFormat: cannot encode an empty record "
                "stream (.mat structured arrays require at least one "
                "row)"
            )
        structured = self._records_to_structured_array(materialised, np)
        buf = io.BytesIO()
        scipy_io.savemat(buf, {self._variable_name: structured})
        return buf.getvalue()

    def _records_to_structured_array(self, records: list[dict[str, Any]], np: Any) -> Any:
        field_order = self._derive_field_order(records)
        dtype_fields: list[tuple[str, Any]] = []
        for field in field_order:
            sample_value = next((rec[field] for rec in records if field in rec), None)
            dtype_fields.append((field, self._infer_numpy_dtype(sample_value, records, field, np)))
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

    def _derive_field_order(self, records: list[dict[str, Any]]) -> list[str]:
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
            # MAT files have no native bool — store as int8.
            return np.int8
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
        return np.float64

    @staticmethod
    def _zero_for_dtype(dtype: Any) -> Any:
        kind = dtype.kind
        if kind == "U":
            return ""
        if kind in ("i", "u"):
            return 0
        if kind == "f":
            return 0.0
        return 0

    @staticmethod
    def _unwrap_matlab_scalar(value: Any, np: Any) -> Any:
        # scipy.io wraps every cell as a 2-D ndarray (typically (1, 1)
        # or (1, N) for strings).
        if isinstance(value, np.ndarray):
            if value.dtype.kind == "U":
                # Concatenate the row of unicode chars / strings.
                if value.size == 0:
                    return ""
                if value.size == 1:
                    return str(value.flat[0])
                return "".join(str(v) for v in value.flat)
            if value.size == 1:
                return MatlabMatFormat._unwrap_matlab_scalar(value.flat[0], np)
            return value
        if isinstance(value, bytes):
            return value.decode("utf-8")
        if hasattr(value, "item"):
            return value.item()
        return value

    @staticmethod
    def _load_scipy_numpy() -> tuple[Any, Any]:
        try:
            import numpy as np
            import scipy.io as scipy_io
        except ImportError as exc:
            raise ImportError(
                "MatlabMatFormat requires scipy. Install with `pip install pirn[matlab]`."
            ) from exc
        return scipy_io, np
