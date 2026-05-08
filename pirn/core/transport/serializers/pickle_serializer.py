"""``PickleSerializer`` — fallback serialiser using Python's pickle protocol.

Used for any value type not covered by a more specific serialiser.
Pickle handles arbitrary Python objects but produces non-portable bytes
(Python version and class path sensitive). Register more specific
serialisers (numpy, arrow, etc.) for types that cross process or
language boundaries.
"""

from __future__ import annotations

import pickle
from typing import Any

from pirn.core.transport.serializers.i_serializer import ISerializer
from pirn.core.transport.serializers.serialiser_error import SerialiserError


class PickleSerializer(ISerializer):
    """Serialise any Python value via ``pickle`` (protocol 5)."""

    def serialise(self, value: Any) -> bytes:
        try:
            return pickle.dumps(value, protocol=5)
        except Exception as exc:
            raise SerialiserError(
                f"PickleSerializer: cannot serialise {type(value).__name__}: {exc}"
            ) from exc

    def deserialise(self, data: bytes, type_name: str) -> Any:
        try:
            return pickle.loads(data)
        except Exception as exc:
            raise SerialiserError(
                f"PickleSerializer: cannot deserialise {type_name}: {exc}"
            ) from exc

    def can_handle(self, value: Any) -> bool:
        return True
