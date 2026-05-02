"""``NiftiFormat`` — NIfTI neuroimaging batch encoder/decoder.

NIfTI (Neuroimaging Informatics Technology Initiative) is the standard
container for MRI, fMRI, and related neuroimaging data. ``nibabel`` is
the reference Python binding; it expects a filesystem path so this
implementation uses a temporary file for I/O.

Records are emitted as ONE record per file with shape::

    {
        "shape":   tuple[int, ...],   # voxel dimensions
        "dtype":   str,               # numpy dtype name
        "affine":  list[list[float]], # 4x4 affine matrix
        "header":  dict,              # selected header fields
        "data":    bytes,             # raw image array bytes
    }

Install: ``pip install pirn[health]``.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class NiftiFormat(BatchFileFormat):
    """Whole-file NIfTI encoder/decoder backed by ``nibabel``."""

    @property
    def name(self) -> str:
        return "nifti"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        nib = self._load_nibabel()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "image.nii"
            path.write_bytes(payload)
            img = nib.load(str(path))
            array = img.get_fdata()
            record: dict[str, Any] = {
                "shape": tuple(int(d) for d in img.shape),
                "dtype": str(array.dtype),
                "affine": img.affine.tolist(),
                "header": self._extract_header(img.header),
                "data": array.tobytes(),
            }
        return [record]

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        nib = self._load_nibabel()
        import numpy as np

        materialised = list(records)
        if not materialised:
            raise ValueError(
                "NiftiFormat: cannot encode an empty record stream."
            )
        record = materialised[0]
        shape = tuple(record["shape"])
        dtype = np.dtype(record["dtype"])
        affine = np.array(record["affine"], dtype=np.float64)
        raw = record["data"]
        if not isinstance(raw, (bytes, bytearray)):
            raise TypeError(
                "NiftiFormat: 'data' must be bytes, got "
                f"{type(raw).__name__}"
            )
        array = np.frombuffer(raw, dtype=dtype).reshape(shape)
        img = nib.Nifti1Image(array, affine)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "image.nii"
            nib.save(img, str(path))
            return path.read_bytes()

    @staticmethod
    def _extract_header(header: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key in header.keys():
            try:
                value = header[key]
                if hasattr(value, "tolist"):
                    result[key] = value.tolist()
                else:
                    result[key] = value
            except Exception:
                pass
        return result

    @staticmethod
    def _load_nibabel() -> Any:
        try:
            import nibabel as nib
        except ImportError as exc:
            raise ImportError(
                "NiftiFormat requires nibabel. Install with "
                "`pip install pirn[health]`."
            ) from exc
        return nib
