"""``NumpySerializer`` — efficient numpy array serialisation via ``numpy.save``.

Uses the ``.npy`` format (numpy's native binary format) which preserves
dtype, shape, and Fortran/C order. Significantly more compact and faster
than pickle for large arrays.

Only registered by :class:`~pirn.core.transport.serializers.serializer_registry.SerializerRegistry`
when ``numpy`` is importable.
"""

from __future__ import annotations

import io
from typing import Any

from pirn.core.transport.serializers.i_serializer import ISerializer
from pirn.core.transport.serializers.serialiser_error import SerialiserError


class NumpySerializer(ISerializer):
    """Serialise ``numpy.ndarray`` values using the ``.npy`` binary format."""

    def serialise(self, value: Any) -> bytes:
        try:
            import numpy as np

            buf = io.BytesIO()
            np.save(buf, value, allow_pickle=False)
            return buf.getvalue()
        except Exception as exc:
            raise SerialiserError(
                f"NumpySerializer: cannot serialise array of dtype "
                f"{getattr(value, 'dtype', '?')} shape {getattr(value, 'shape', '?')}: {exc}"
            ) from exc

    def deserialise(self, data: bytes, type_name: str) -> Any:
        try:
            import numpy as np

            buf = io.BytesIO(data)
            return np.load(buf, allow_pickle=False)
        except Exception as exc:
            raise SerialiserError(
                f"NumpySerializer: cannot deserialise numpy array: {exc}"
            ) from exc

    def can_handle(self, value: Any) -> bool:
        try:
            import numpy as np

            return isinstance(value, np.ndarray)
        except ImportError:
            return False
