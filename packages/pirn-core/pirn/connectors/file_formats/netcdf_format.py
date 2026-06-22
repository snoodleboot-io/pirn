"""``NetcdfFormat`` — NetCDF-4 batch encoder/decoder.

NetCDF-4 is HDF5-on-the-wire with a self-describing scientific schema
on top. The reference Python binding, ``netCDF4``, links the C library
directly: it requires a real filesystem path and **does not** accept
:class:`io.BytesIO`. To preserve the streaming-bytes contract demanded
by :class:`pirn.connectors.file_format.FileFormat`, the encode
and decode paths use a private temporary file that is removed in a
``finally`` block, so payloads never linger on disk.

Records are stored as one variable (default name ``"data"``) of a
NetCDF compound type defined inline from the inferred numpy structured
dtype.

Install: ``pip install pirn[netcdf]``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class NetcdfFormat(BatchFileFormat):
    """Whole-file NetCDF-4 encoder/decoder backed by ``netCDF4``.

    Args:
        variable_name: Name of the compound-type variable that holds
            the records. Must be a non-empty string.
        dimension_name: Name of the row dimension that the variable is
            indexed by. Must be a non-empty string.
        compound_type_name: Name registered for the compound type
            backing the variable. Must be a non-empty string.
        field_names: Optional ordered tuple of column names. Used as
            field order at encode time when supplied.
    """

    def __init__(
        self,
        variable_name: str = "data",
        dimension_name: str = "row",
        compound_type_name: str = "record_t",
        field_names: Sequence[str] | None = None,
    ) -> None:
        if not isinstance(variable_name, str) or not variable_name:
            raise ValueError("NetcdfFormat: variable_name must be a non-empty string")
        if not isinstance(dimension_name, str) or not dimension_name:
            raise ValueError("NetcdfFormat: dimension_name must be a non-empty string")
        if not isinstance(compound_type_name, str) or not compound_type_name:
            raise ValueError("NetcdfFormat: compound_type_name must be a non-empty string")
        if field_names is not None:
            if not isinstance(field_names, Sequence) or isinstance(field_names, (str, bytes)):
                raise TypeError(
                    "NetcdfFormat: field_names must be a sequence of "
                    f"strings, got {type(field_names).__name__}"
                )
            for name in field_names:
                if not isinstance(name, str) or not name:
                    raise ValueError(
                        f"NetcdfFormat: every field name must be a non-empty string, got {name!r}"
                    )
        self._variable_name = variable_name
        self._dimension_name = dimension_name
        self._compound_type_name = compound_type_name
        self._field_names: tuple[str, ...] | None = (
            tuple(field_names) if field_names is not None else None
        )

    @property
    def name(self) -> str:
        return "netcdf"

    @property
    def variable_name(self) -> str:
        return self._variable_name

    @property
    def dimension_name(self) -> str:
        return self._dimension_name

    @property
    def compound_type_name(self) -> str:
        return self._compound_type_name

    @property
    def field_names(self) -> tuple[str, ...] | None:
        return self._field_names

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        netcdf4_lib, np = self._load_netcdf_numpy()
        # netcdf4_lib demands a filesystem path; round-trip via a tempfile
        # (cleaned up in finally so payloads never linger on disk).
        tmp_path = self._write_temp_payload(payload)
        try:
            dataset = netcdf4_lib.Dataset(tmp_path, "r")
            try:
                if self._variable_name not in dataset.variables:
                    raise ValueError(
                        "NetcdfFormat: variable "
                        f"{self._variable_name!r} not found; "
                        "available: "
                        f"{list(dataset.variables.keys())}"
                    )
                variable = dataset.variables[self._variable_name]
                data = variable[:]
                if data.dtype.names is None:
                    raise ValueError(
                        "NetcdfFormat: variable "
                        f"{self._variable_name!r} is not a structured "
                        "(compound) array; cannot reconstruct records"
                    )
                records: list[Mapping[str, Any]] = []
                for row in data:
                    record: dict[str, Any] = {}
                    for field in data.dtype.names:
                        record[field] = self._unwrap_scalar(row[field], np)
                    records.append(record)
                return records
            finally:
                dataset.close()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        netcdf4_lib, np = self._load_netcdf_numpy()
        materialised = [dict(record) for record in records]
        if not materialised:
            raise ValueError(
                "NetcdfFormat: cannot encode an empty record stream "
                "(NetCDF compound variables require at least one row)"
            )
        structured = self._records_to_structured_array(materialised, np)
        # mkstemp creates the file atomically with 0600 perms (no mktemp race);
        # close our handle so the netCDF4 "w" open can overwrite the path.
        fd, tmp_path = tempfile.mkstemp(suffix=".nc")
        os.close(fd)
        try:
            dataset = netcdf4_lib.Dataset(tmp_path, "w", format="NETCDF4")
            try:
                dataset.createDimension(self._dimension_name, len(materialised))
                compound = dataset.createCompoundType(structured.dtype, self._compound_type_name)
                variable = dataset.createVariable(
                    self._variable_name,
                    compound,
                    (self._dimension_name,),
                )
                variable[:] = structured
            finally:
                dataset.close()
            with open(tmp_path, "rb") as fh:
                return fh.read()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

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
                    value = record[field]
                    structured[index][field] = (
                        value.encode("utf-8")
                        if isinstance(value, str) and structured.dtype.fields[field][0].kind == "S"
                        else value
                    )
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
            # NetCDF compound types do not support bool natively;
            # store as int8 (1/0). Round-trip will return ``int``.
            return np.int8
        if isinstance(sample_value, int):
            return np.int64
        if isinstance(sample_value, float):
            return np.float64
        if isinstance(sample_value, str):
            max_len = max(
                (
                    len(rec[field].encode("utf-8"))
                    for rec in records
                    if isinstance(rec.get(field), str)
                ),
                default=1,
            )
            # NetCDF compound types use fixed-width byte strings;
            # decoded back to ``str`` on read.
            return f"S{max(max_len, 1)}"
        return np.float64

    @staticmethod
    def _zero_for_dtype(dtype: Any) -> Any:
        kind = dtype.kind
        if kind in ("U", "S"):
            return b"" if kind == "S" else ""
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
            return NetcdfFormat._unwrap_scalar(value.item(), np)
        if hasattr(value, "item"):
            return value.item()
        return value

    @staticmethod
    def _write_temp_payload(payload: bytes) -> str:
        # mkstemp creates the file atomically with 0600 perms (no mktemp race).
        fd, tmp_path = tempfile.mkstemp(suffix=".nc")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
        except BaseException:
            os.remove(tmp_path)
            raise
        return tmp_path

    @staticmethod
    def _load_netcdf_numpy() -> tuple[Any, Any]:
        try:
            import netCDF4 as netcdf4_lib
            import numpy as np
        except ImportError as exc:
            raise ImportError(
                "NetcdfFormat requires netCDF4 and numpy. Install with `pip install pirn[netcdf]`."
            ) from exc
        return netcdf4_lib, np
