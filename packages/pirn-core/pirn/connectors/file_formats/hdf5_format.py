"""``Hdf5Format`` — Hierarchical Data Format v5 batch encoder/decoder.

HDF5 is a binary container with an internal directory tree. ``h5py`` is
the de-facto Python binding; it accepts ``io.BytesIO`` for reads and
writes against the in-memory file driver. The whole payload must be
buffered before decoding — the file's central directory may live at
arbitrary offsets — so this is a :class:`BatchFileFormat`.

Records are represented as rows of a numpy structured array stored at
``dataset_path``. Field names come from the first record's keys (or all
records' union, ordered by first appearance) and dtypes are inferred
from values.

Install: ``pip install "pirn-core[hdf5]"``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, ClassVar

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.payload_shape import PayloadShape
from pirn.core.optional_dependency import OptionalDependency

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt


class Hdf5Format(BatchFileFormat):
    """Whole-file HDF5 encoder/decoder backed by ``h5py``.

    Args:
        dataset_path: HDF5-internal path (POSIX-style) where the
            structured-array dataset is stored. Must be non-empty and
            start with ``/`` to be unambiguous; a leading ``/`` is added
            automatically if missing.
        compression: Optional ``h5py`` compression filter name
            (``"gzip"``, ``"lzf"``, or ``"szip"``). ``None`` writes
            uncompressed. Supported values match ``h5py``'s built-in
            filters.
    """

    _supported_compression: ClassVar[frozenset[str]] = frozenset({"gzip", "lzf", "szip"})

    def __init__(
        self,
        dataset_path: str = "/data",
        compression: str | None = None,
    ) -> None:
        if not isinstance(dataset_path, str) or not dataset_path:
            raise ValueError("Hdf5Format: dataset_path must be a non-empty string")
        if compression is not None:
            if not isinstance(compression, str):
                raise TypeError(
                    f"Hdf5Format: compression must be str | None, got {type(compression).__name__}"
                )
            if compression not in self._supported_compression:
                raise ValueError(
                    "Hdf5Format: compression must be one of "
                    f"{sorted(self._supported_compression)} or None, "
                    f"got {compression!r}"
                )
        self._dataset_path = dataset_path if dataset_path.startswith("/") else f"/{dataset_path}"
        self._compression = compression

    @property
    def name(self) -> str:
        return "hdf5"

    @property
    def dataset_path(self) -> str:
        return self._dataset_path

    @property
    def compression(self) -> str | None:
        return self._compression

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        h5py = OptionalDependency.require("h5py", extra="hdf5")
        records: list[Mapping[str, Any]] = []
        with h5py.File(io.BytesIO(payload), "r") as handle:
            if self._dataset_path not in handle:
                raise ValueError(
                    "Hdf5Format: dataset "
                    f"{self._dataset_path!r} not found; available: "
                    f"{list(handle.keys())}"
                )
            dataset = handle[self._dataset_path]
            data = dataset[()]
            field_names = data.dtype.names if data.dtype.names is not None else None
            if field_names is None:
                raise ValueError(
                    "Hdf5Format: dataset is not a structured array; cannot reconstruct records"
                )
            for row in data:
                record: dict[str, Any] = {}
                for field in field_names:
                    record[field] = self._unwrap_scalar(row[field])
                records.append(record)
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        h5py = OptionalDependency.require("h5py", extra="hdf5")
        materialised = [dict(record) for record in records]
        if not materialised:
            raise ValueError(
                "Hdf5Format: cannot encode an empty record stream "
                "(HDF5 structured arrays require at least one row)"
            )
        structured = self._records_to_structured_array(materialised)
        buf = io.BytesIO()
        with h5py.File(buf, "w") as handle:
            kwargs: dict[str, Any] = {}
            if self._compression is not None:
                kwargs["compression"] = self._compression
            handle.create_dataset(self._dataset_path, data=structured, **kwargs)
        return buf.getvalue()

    @classmethod
    def _records_to_structured_array(cls, records: list[dict[str, Any]]) -> npt.NDArray[np.void]:
        import numpy as np

        field_order: list[str] = []
        seen: set[str] = set()
        for record in records:
            for key in record.keys():
                if key not in seen:
                    seen.add(key)
                    field_order.append(key)
        # HDF5 cannot store numpy unicode (U) dtype directly; encode
        # str fields as variable-length UTF-8 byte strings using
        # h5py's vlen string type.
        string_fields: set[str] = set()
        dtype_fields: list[tuple[str, type[np.generic] | str]] = []
        for field in field_order:
            sample_value = next((rec[field] for rec in records if field in rec), None)
            field_dtype = cls._infer_numpy_dtype(sample_value, records, field)
            if isinstance(sample_value, str):
                string_fields.add(field)
            dtype_fields.append((field, field_dtype))
        zero_values = {field: cls._zero_for_dtype(np.dtype(spec)) for field, spec in dtype_fields}
        structured = np.zeros(len(records), dtype=dtype_fields)
        for index, record in enumerate(records):
            for field in field_order:
                if field in record:
                    value = record[field]
                    if field in string_fields and isinstance(value, str):
                        structured[index][field] = value.encode("utf-8")
                    else:
                        structured[index][field] = value
                else:
                    structured[index][field] = zero_values[field]
        return structured

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
                (
                    len(rec[field].encode("utf-8"))
                    for rec in records
                    if isinstance(rec.get(field), str)
                ),
                default=1,
            )
            # Fixed-width byte string; HDF5 does not natively support
            # numpy unicode dtype. Decoded back to ``str`` on read.
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
        if PayloadShape.is_ndarray(value) and value.shape == ():
            return cls._unwrap_scalar(value.item())
        if hasattr(value, "item"):
            return value.item()
        return value
