"""``RootFormat`` — CERN ROOT batch decoder (read-only).

ROOT is the de-facto data format in high-energy particle physics,
storing TTrees (n-tuples) and histograms. The reference Python binding
is ``uproot``.

Records are emitted as ONE record per TTree found in the file::

    {
        "tree_name": str,
        "n_entries": int,
        "branches":  list[str],
        "data":      dict[str, bytes],  # branch name → numpy array bytes
    }

Write is not supported because producing valid ROOT files requires the
``uproot`` write API combined with ``awkward-array``, which adds
substantial complexity outside the scope of this connector.

Install: ``pip install pirn[physics]``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class RootFormat(BatchFileFormat):
    """Whole-file CERN ROOT decoder backed by ``uproot``.

    Decode emits one record per TTree. Encode is not supported.
    """

    @property
    def name(self) -> str:
        return "root"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        uproot = self._load_uproot()
        tmp_path = self._write_temp(payload, ".root")
        records: list[Mapping[str, Any]] = []
        try:
            with uproot.open(tmp_path) as f:
                for key in f.keys(cycle=False):
                    obj = f[key]
                    if not hasattr(obj, "keys"):
                        continue
                    try:
                        branch_names = obj.keys()
                    except (AttributeError, ValueError):
                        continue
                    n_entries: int = 0
                    try:
                        n_entries = int(obj.num_entries)
                    except (AttributeError, ValueError, TypeError):
                        pass
                    data: dict[str, bytes] = {}
                    for branch_name in branch_names:
                        try:
                            arr = obj[branch_name].array(library="np")
                            data[branch_name] = arr.tobytes()
                        except (AttributeError, ValueError, MemoryError, KeyError):
                            data[branch_name] = b""
                    records.append(
                        {
                            "tree_name": str(key),
                            "n_entries": n_entries,
                            "branches": list(branch_names),
                            "data": data,
                        }
                    )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        return records

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        raise NotImplementedError(
            "RootFormat: write is not supported — ROOT files require "
            "uproot4 + awkward"
        )

    @staticmethod
    def _write_temp(payload: bytes, suffix: str) -> str:
        tmp_path = tempfile.mktemp(suffix=suffix)
        with open(tmp_path, "wb") as fh:
            fh.write(payload)
        return tmp_path

    @staticmethod
    def _load_uproot() -> Any:
        try:
            import uproot
        except ImportError as exc:
            raise ImportError(
                "RootFormat requires uproot. Install with "
                "`pip install pirn[physics]`."
            ) from exc
        return uproot
