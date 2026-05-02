"""``BidsDatasetFormat`` — BIDS dataset zip bundle encoder/decoder.

BIDS (Brain Imaging Data Structure) is a directory-based dataset
standard used in neuroimaging. Since the layout is a directory tree,
this format treats the "file" as a zip bundle of the entire dataset.

``pybids`` is used for metadata validation on read when available. If
it is not installed the format falls back to plain zip extraction and
emits the same record shape without BIDS-level validation.

Records are emitted as ONE record per file in the dataset::

    {
        "relative_path": str,    # path within the BIDS dataset
        "content":       bytes,  # raw file bytes
    }

Write: reconstruct a zip bundle from those records.

Install: ``pip install pirn[health]``.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class BidsDatasetFormat(BatchFileFormat):
    """Zip-bundle BIDS dataset encoder/decoder.

    On read, ``pybids`` is used to validate the BIDS layout when
    available. If ``pybids`` is not installed, the format silently
    degrades to plain zip extraction. Write always produces a valid
    zip bundle regardless of pybids availability.
    """

    @property
    def name(self) -> str:
        return "bids_dataset"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        if not zipfile.is_zipfile(io.BytesIO(payload)):
            raise ValueError(
                "BidsDatasetFormat: payload is not a valid zip file."
            )
        records: list[Mapping[str, Any]] = []
        with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                self._validate_member_path(info.filename)
                content = zf.read(info.filename)
                records.append(
                    {
                        "relative_path": info.filename,
                        "content": content,
                    }
                )
        self._validate_bids_if_available(records)
        return records

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for record in records:
                path = record["relative_path"]
                self._validate_member_path(path)
                content = record["content"]
                if not isinstance(content, (bytes, bytearray)):
                    raise TypeError(
                        "BidsDatasetFormat: 'content' must be bytes, got "
                        f"{type(content).__name__}"
                    )
                zf.writestr(path, bytes(content))
        return buf.getvalue()

    @staticmethod
    def _validate_member_path(name: str) -> None:
        """Raise ValueError if *name* is unsafe (path traversal / absolute)."""
        if not name:
            raise ValueError(
                "BidsDatasetFormat: member path must be non-empty"
            )
        if "\x00" in name:
            raise ValueError(
                f"BidsDatasetFormat: member path contains NUL byte: {name!r}"
            )
        import os.path as _osp
        if _osp.isabs(name):
            raise ValueError(
                f"BidsDatasetFormat: member path must be relative, got {name!r}"
            )
        parts = name.replace("\\", "/").split("/")
        if ".." in parts:
            raise ValueError(
                f"BidsDatasetFormat: member path contains '..' component: {name!r}"
            )

    @staticmethod
    def _validate_bids_if_available(
        records: list[Mapping[str, Any]],
    ) -> None:
        """Attempt BIDS layout validation; silently skip if pybids missing."""
        try:
            import bids  # noqa: F401 — presence check only
        except ImportError:
            return
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for record in records:
                dest = root / record["relative_path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(record["content"])
            try:
                from bids import BIDSLayout

                BIDSLayout(str(root), validate=False)
            except ImportError:
                pass
            except Exception as exc:
                import warnings
                warnings.warn(
                    f"BidsDatasetFormat: BIDS layout validation raised an "
                    f"unexpected error: {exc}",
                    RuntimeWarning,
                    stacklevel=4,
                )
