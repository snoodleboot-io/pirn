"""``BidsDatasetFormat`` — BIDS dataset zip bundle encoder/decoder.

BIDS (Brain Imaging Data Structure) is a directory-based dataset
standard used in neuroimaging. Since the layout is a directory tree,
this format treats the "file" as a zip bundle of the entire dataset.

Layout validation is opt-in: ``BidsDatasetFormat(validate=True)`` runs the
bundle through ``pybids`` on read and raises when the tree does not satisfy
the BIDS standard. It is off by default because most callers use this format
to move a dataset, not to certify one — but when it is on it is real: it
requires ``pybids`` (naming the install hint if absent) and it raises rather
than warns (PIR-873).

Records are emitted as ONE record per file in the dataset::

    {
        "relative_path": str,    # path within the BIDS dataset
        "content":       bytes,  # raw file bytes
    }

Write: reconstruct a zip bundle from those records.

Install: ``pip install "pirn-core[bids]"`` — required for ``validate=True``.
"""

from __future__ import annotations

import io
import os.path
import tempfile
import zipfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.core.optional_dependency import OptionalDependency


class BidsDatasetFormat(BatchFileFormat):
    """Zip-bundle BIDS dataset encoder/decoder.

    Reading and writing the bundle needs no optional backend. Pass
    ``validate=True`` to additionally check the decoded tree against the BIDS
    standard with ``pybids``; that check requires the ``bids`` extra and raises
    on a dataset that does not satisfy it.

    One record is emitted per file in the dataset::

        {
            "relative_path":  str,    # path within the BIDS zip bundle
            "content":        bytes,  # raw file bytes
        }

    Encoding reconstructs the zip bundle from the same shape.
    """

    def __init__(self, *, validate: bool = False) -> None:
        """Configure the codec.

        Args:
            validate: When ``True``, :meth:`_decode_full` checks the decoded
                tree against the BIDS standard with ``pybids`` and raises if it
                does not satisfy it. Requires the ``bids`` extra.

        Raises:
            TypeError: If ``validate`` is not a ``bool``.
        """
        if not isinstance(validate, bool):
            raise TypeError(
                f"BidsDatasetFormat: validate must be bool, got {type(validate).__name__}"
            )
        self._validate = validate

    @property
    def name(self) -> str:
        return "bids_dataset"

    @property
    def validate(self) -> bool:
        """Whether :meth:`_decode_full` checks the decoded tree with ``pybids``."""
        return self._validate

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not zipfile.is_zipfile(io.BytesIO(payload)):
            raise ValueError("BidsDatasetFormat: payload is not a valid zip file.")
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
        if self._validate:
            self._validate_bids_layout(records)
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for record in records:
                path = record["relative_path"]
                self._validate_member_path(path)
                content = record["content"]
                if not isinstance(content, (bytes, bytearray)):
                    raise TypeError(
                        f"BidsDatasetFormat: 'content' must be bytes, got {type(content).__name__}"
                    )
                zf.writestr(path, bytes(content))
        return buf.getvalue()

    @staticmethod
    def _validate_member_path(name: str) -> None:
        """Raise ValueError if *name* is unsafe (path traversal / absolute)."""
        if not name:
            raise ValueError("BidsDatasetFormat: member path must be non-empty")
        if "\x00" in name:
            raise ValueError(f"BidsDatasetFormat: member path contains NUL byte: {name!r}")
        if os.path.isabs(name):
            raise ValueError(f"BidsDatasetFormat: member path must be relative, got {name!r}")
        parts = name.replace("\\", "/").split("/")
        if ".." in parts:
            raise ValueError(f"BidsDatasetFormat: member path contains '..' component: {name!r}")

    @staticmethod
    def _validate_bids_layout(records: list[Mapping[str, Any]]) -> None:
        """Check the decoded tree against the BIDS standard, raising when it fails.

        Three things this deliberately does not do, each of which it used to
        (PIR-873):

        * skip silently when ``pybids`` is absent — a caller that asked for
          validation gets the install hint, not an unvalidated dataset;
        * pass ``validate=False`` to ``BIDSLayout``, which turns the standard's
          own checks off and made this method validate nothing at all;
        * downgrade a failure to a ``RuntimeWarning``, which a pipeline does not
          see.

        Args:
            records: The decoded ``relative_path`` / ``content`` records.

        Raises:
            ImportError: If ``pybids`` is not installed.
            ValueError: If the tree does not satisfy the BIDS standard.
        """
        bids = OptionalDependency.require("bids", extra="bids")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for record in records:
                dest = root / record["relative_path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(record["content"])
            try:
                bids.BIDSLayout(str(root), validate=True)
            except Exception as exc:
                raise ValueError(
                    f"BidsDatasetFormat: the dataset does not satisfy the BIDS standard: {exc}"
                ) from exc
