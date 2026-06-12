"""``AsdfFormat`` — Advanced Scientific Data Format batch encoder/decoder.

ASDF is a next-generation scientific data format used in astronomy and
space science (e.g. JWST pipeline). It stores metadata as YAML with
binary array blocks inline. The reference Python binding is ``asdf``.

Records are emitted as ONE record that is the full ASDF tree as a dict.
Binary array blocks are serialised as ``bytes`` items in the dict.

Install: ``pip install pirn[astronomy]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class AsdfFormat(BatchFileFormat):
    """Whole-file ASDF encoder/decoder backed by ``asdf``.

    Decode emits a single record containing the full ASDF tree. Arrays
    are serialised as raw bytes. Encode reconstructs the ASDF file from
    that single record dict.
    """

    @property
    def name(self) -> str:
        return "asdf"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        asdf_mod = self._load_asdf()
        import numpy as np

        with asdf_mod.open(io.BytesIO(payload)) as af:
            tree = self._serialise_tree(dict(af.tree), np)
        return [tree]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        asdf_mod = self._load_asdf()
        import numpy as np

        materialised = [dict(record) for record in records]
        if not materialised:
            tree: dict[str, Any] = {}
        else:
            tree = self._deserialise_tree(materialised[0], np)
        af = asdf_mod.AsdfFile(tree)
        buf = io.BytesIO()
        af.write_to(buf)
        return buf.getvalue()

    @classmethod
    def _serialise_tree(cls, obj: Any, np: Any) -> Any:
        """Recursively convert numpy arrays to bytes for serialisation."""
        if isinstance(obj, np.ndarray):
            return obj.tobytes()
        if isinstance(obj, dict):
            return {k: cls._serialise_tree(v, np) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            converted = [cls._serialise_tree(item, np) for item in obj]
            return type(obj)(converted)
        return obj

    @classmethod
    def _deserialise_tree(cls, obj: Any, np: Any) -> Any:
        """Recursively pass through tree; bytes stay as bytes for asdf."""
        if isinstance(obj, dict):
            return {k: cls._deserialise_tree(v, np) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            converted = [cls._deserialise_tree(item, np) for item in obj]
            return type(obj)(converted)
        return obj

    @staticmethod
    def _load_asdf() -> Any:
        try:
            import asdf
        except ImportError as exc:
            raise ImportError(
                "AsdfFormat requires asdf. Install with `pip install pirn[astronomy]`."
            ) from exc
        return asdf
