"""``AsdfFormat`` — Advanced Scientific Data Format batch encoder/decoder.

ASDF is a next-generation scientific data format used in astronomy and
space science (e.g. JWST pipeline). It stores metadata as YAML with
binary array blocks inline. The reference Python binding is ``asdf``.

Records are emitted as ONE record that is the full ASDF tree as a dict.
Binary array blocks are serialised as ``bytes`` items in the dict.

Install: ``pip install "pirn-core[asdf]"``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.payload_shape import PayloadShape
from pirn.core.optional_dependency import OptionalDependency
from pirn.core.shape_guard import ShapeGuard


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
        asdf_mod = OptionalDependency.require("asdf", extra="asdf")
        with asdf_mod.open(io.BytesIO(payload)) as af:
            source: dict[str, object] = dict(af.tree)
            tree: dict[str, Any] = {
                key: self._serialise_tree(value) for key, value in source.items()
            }
        return [tree]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        asdf_mod = OptionalDependency.require("asdf", extra="asdf")
        materialised = [dict(record) for record in records]
        tree: dict[str, object] = {}
        if materialised:
            tree = {key: self._deserialise_tree(value) for key, value in materialised[0].items()}
        af = asdf_mod.AsdfFile(tree)
        buf = io.BytesIO()
        af.write_to(buf)
        return buf.getvalue()

    @classmethod
    def _serialise_tree(cls, obj: object) -> object:
        """Recursively convert numpy arrays to bytes for serialisation."""
        if PayloadShape.is_ndarray(obj):
            return obj.tobytes()
        if ShapeGuard.is_dict(obj):
            return {key: cls._serialise_tree(value) for key, value in obj.items()}
        if ShapeGuard.is_list(obj):
            return [cls._serialise_tree(item) for item in obj]
        if ShapeGuard.is_tuple(obj):
            return tuple(cls._serialise_tree(item) for item in obj)
        return obj

    @classmethod
    def _deserialise_tree(cls, obj: object) -> object:
        """Recursively pass through tree; bytes stay as bytes for asdf."""
        if ShapeGuard.is_dict(obj):
            return {key: cls._deserialise_tree(value) for key, value in obj.items()}
        if ShapeGuard.is_list(obj):
            return [cls._deserialise_tree(item) for item in obj]
        if ShapeGuard.is_tuple(obj):
            return tuple(cls._deserialise_tree(item) for item in obj)
        return obj
