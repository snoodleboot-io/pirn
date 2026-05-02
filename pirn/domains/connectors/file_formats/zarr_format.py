"""``ZarrFormat`` — Zarr v3 zip-store batch encoder/decoder.

Zarr is natively a *directory* layout (one file per chunk). For
single-file IO we use ``zarr.storage.ZipStore``, which packages the
directory as a deflate-free zip archive. Zarr v3's ZipStore wants a
filesystem path (it does not accept :class:`io.BytesIO`); we therefore
write/read through a private temporary file. The file is removed in a
``finally`` block so payloads never linger on disk.

Records are stored as a single named structured-array dataset under
``dataset_path`` (default ``"data"``) inside the zip-store root group.

Install: ``pip install pirn[zarr]``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class ZarrFormat(BatchFileFormat):
    """Whole-file Zarr (zip-store) encoder/decoder.

    Args:
        dataset_path: Name of the array inside the root Zarr group
            where records are stored. Must be a non-empty string.
        chunks: Optional explicit chunk shape forwarded to the Zarr
            array constructor. ``None`` lets Zarr choose a default
            chunk shape (typically the whole array).
        field_names: Optional ordered tuple of column names. Used as
            field order at encode time when supplied.
    """

    def __init__(
        self,
        dataset_path: str = "data",
        chunks: tuple[int, ...] | None = None,
        field_names: Sequence[str] | None = None,
    ) -> None:
        if not isinstance(dataset_path, str) or not dataset_path:
            raise ValueError(
                "ZarrFormat: dataset_path must be a non-empty string"
            )
        if chunks is not None:
            if not isinstance(chunks, tuple):
                raise TypeError(
                    "ZarrFormat: chunks must be a tuple of positive "
                    f"ints or None, got {type(chunks).__name__}"
                )
            for chunk in chunks:
                if (
                    not isinstance(chunk, int)
                    or isinstance(chunk, bool)
                    or chunk <= 0
                ):
                    raise ValueError(
                        "ZarrFormat: every chunk dimension must be a "
                        f"positive int, got {chunk!r}"
                    )
        if field_names is not None:
            if not isinstance(field_names, Sequence) or isinstance(
                field_names, (str, bytes)
            ):
                raise TypeError(
                    "ZarrFormat: field_names must be a sequence of "
                    f"strings, got {type(field_names).__name__}"
                )
            for name in field_names:
                if not isinstance(name, str) or not name:
                    raise ValueError(
                        "ZarrFormat: every field name must be a "
                        f"non-empty string, got {name!r}"
                    )
        self._dataset_path = dataset_path
        self._chunks = chunks
        self._field_names: tuple[str, ...] | None = (
            tuple(field_names) if field_names is not None else None
        )

    @property
    def name(self) -> str:
        return "zarr"

    @property
    def dataset_path(self) -> str:
        return self._dataset_path

    @property
    def chunks(self) -> tuple[int, ...] | None:
        return self._chunks

    @property
    def field_names(self) -> tuple[str, ...] | None:
        return self._field_names

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        zarr_module, np = self._load_zarr_numpy()
        # ZipStore needs a filesystem path; write the payload through a
        # named tempfile and clean up on the way out.
        tmp_path = self._write_temp_payload(payload)
        try:
            store = zarr_module.storage.ZipStore(tmp_path, mode="r")
            try:
                root = zarr_module.open_group(store=store, mode="r")
                if self._dataset_path not in root:
                    raise ValueError(
                        "ZarrFormat: dataset "
                        f"{self._dataset_path!r} not found; available: "
                        f"{list(root.array_keys())}"
                    )
                array = root[self._dataset_path]
                data = array[:]
                if data.dtype.names is None:
                    raise ValueError(
                        "ZarrFormat: dataset "
                        f"{self._dataset_path!r} is not a structured "
                        "array; cannot reconstruct records"
                    )
                records: list[Mapping[str, Any]] = []
                for row in data:
                    record: dict[str, Any] = {}
                    for field in data.dtype.names:
                        record[field] = self._unwrap_scalar(
                            row[field], np
                        )
                    records.append(record)
                return records
            finally:
                store.close()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        zarr_module, np = self._load_zarr_numpy()
        materialised = [dict(record) for record in records]
        if not materialised:
            raise ValueError(
                "ZarrFormat: cannot encode an empty record stream "
                "(zarr structured arrays require at least one row)"
            )
        structured = self._records_to_structured_array(materialised, np)
        tmp_path = tempfile.mktemp(suffix=".zarr.zip")
        try:
            store = zarr_module.storage.ZipStore(tmp_path, mode="w")
            try:
                root = zarr_module.group(
                    store=store, overwrite=True
                )
                array_kwargs: dict[str, Any] = {
                    "name": self._dataset_path,
                    "shape": structured.shape,
                    "dtype": structured.dtype,
                }
                if self._chunks is not None:
                    array_kwargs["chunks"] = self._chunks
                array = root.create_array(**array_kwargs)
                array[:] = structured
            finally:
                store.close()
            with open(tmp_path, "rb") as fh:
                return fh.read()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

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
        return np.float64

    @staticmethod
    def _zero_for_dtype(dtype: Any) -> Any:
        kind = dtype.kind
        if kind == "U":
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
            return ZarrFormat._unwrap_scalar(value.item(), np)
        if hasattr(value, "item"):
            return value.item()
        return value

    @staticmethod
    def _write_temp_payload(payload: bytes) -> str:
        tmp_path = tempfile.mktemp(suffix=".zarr.zip")
        with open(tmp_path, "wb") as fh:
            fh.write(payload)
        return tmp_path

    @staticmethod
    def _load_zarr_numpy() -> tuple[Any, Any]:
        try:
            import numpy as np
            import zarr
            import zarr.storage  # registers ZipStore on the zarr namespace
        except ImportError as exc:
            raise ImportError(
                "ZarrFormat requires zarr and numpy. Install with "
                "`pip install pirn[zarr]`."
            ) from exc
        return zarr, np
