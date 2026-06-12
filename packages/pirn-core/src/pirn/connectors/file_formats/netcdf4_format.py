"""``Netcdf4Format`` — Multi-group NetCDF4 batch encoder/decoder.

NetCDF4 supports hierarchical groups (similar to HDF5 directories).
This format handles MULTI-GROUP files, emitting one record per
group/variable combination. It is distinct from :class:`NetcdfFormat`
which handles single-group files with compound-type variables.

Records are emitted with shape::

    {
        "group_path":     str,            # "/" or "/group/subgroup"
        "variable_name":  str,
        "dimensions":     list[str],
        "shape":          tuple[int, ...],
        "dtype":          str,
        "data":           bytes,
    }

Install: ``pip install pirn[netcdf]``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class Netcdf4Format(BatchFileFormat):
    """Whole-file multi-group NetCDF4 encoder/decoder backed by ``netCDF4``.

    Decode traverses all groups recursively and emits one record per
    variable. Encode reconstructs a NetCDF4 file creating groups and
    variables as described by the records.
    """

    @property
    def name(self) -> str:
        return "netcdf4"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        netcdf4_lib = self._load_netcdf4()
        tmp_path = self._write_temp(payload, ".nc")
        records: list[Mapping[str, Any]] = []
        try:
            ds = netcdf4_lib.Dataset(tmp_path, "r")
            try:
                self._collect_group(ds, "/", records)
            finally:
                ds.close()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        netcdf4_lib = self._load_netcdf4()
        materialised = [dict(record) for record in records]
        # mkstemp creates the file atomically with 0600 perms (no mktemp race);
        # close our handle so the netCDF4 "w" open can overwrite the path.
        fd, tmp_path = tempfile.mkstemp(suffix=".nc")
        os.close(fd)
        try:
            ds = netcdf4_lib.Dataset(tmp_path, "w", format="NETCDF4")
            try:
                for record in materialised:
                    self._write_record(ds, record, netcdf4_lib)
            finally:
                ds.close()
            with open(tmp_path, "rb") as fh:
                return fh.read()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @classmethod
    def _collect_group(
        cls,
        group: Any,
        group_path: str,
        records: list[Mapping[str, Any]],
    ) -> None:
        import numpy as np

        for var_name, var in group.variables.items():
            data_array = var[:]
            if hasattr(data_array, "filled"):
                data_array = data_array.filled(0)
            records.append(
                {
                    "group_path": group_path,
                    "variable_name": var_name,
                    "dimensions": list(var.dimensions),
                    "shape": tuple(int(d) for d in var.shape),
                    "dtype": str(np.dtype(var.dtype)),
                    "data": np.asarray(data_array).tobytes(),
                }
            )
        for sub_name, sub_group in group.groups.items():
            sub_path = (
                group_path.rstrip("/") + "/" + sub_name if group_path != "/" else "/" + sub_name
            )
            cls._collect_group(sub_group, sub_path, records)

    @staticmethod
    def _resolve_or_create_group(ds: Any, group_path: str) -> Any:
        """Return the netCDF4 group for *group_path*, creating if needed."""
        if group_path in ("/", ""):
            return ds
        parts = [p for p in group_path.split("/") if p]
        current = ds
        for part in parts:
            if part in current.groups:
                current = current.groups[part]
            else:
                current = current.createGroup(part)
        return current

    @classmethod
    def _write_record(cls, ds: Any, record: Mapping[str, Any], netcdf4_lib: Any) -> None:
        import numpy as np

        group_path = record.get("group_path", "/")
        var_name = record["variable_name"]
        dimensions: list[str] = list(record.get("dimensions") or [])
        shape: tuple[int, ...] = tuple(record.get("shape") or ())
        dtype_str: str = str(record.get("dtype", "float64"))
        data_bytes: bytes = record.get("data", b"")

        group = cls._resolve_or_create_group(ds, group_path)

        # Create dimensions that don't already exist in this group
        for dim_name, dim_size in zip(dimensions, shape, strict=False):
            if dim_name not in group.dimensions:
                group.createDimension(dim_name, dim_size)

        dtype = np.dtype(dtype_str)
        var = group.createVariable(var_name, dtype, tuple(dimensions))

        if data_bytes:
            arr = np.frombuffer(data_bytes, dtype=dtype).reshape(shape)
            var[:] = arr

    @staticmethod
    def _write_temp(payload: bytes, suffix: str) -> str:
        # mkstemp creates the file atomically with 0600 perms (no mktemp race).
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
        except BaseException:
            os.remove(tmp_path)
            raise
        return tmp_path

    @staticmethod
    def _load_netcdf4() -> Any:
        try:
            import netCDF4 as netcdf4_lib
        except ImportError as exc:
            raise ImportError(
                "Netcdf4Format requires netCDF4. Install with `pip install pirn[netcdf]`."
            ) from exc
        return netcdf4_lib
