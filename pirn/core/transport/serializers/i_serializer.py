"""``ISerializer`` — abstract contract for value serialisation within transports."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ISerializer(ABC):
    """Converts Python values to bytes and back.

    Each concrete serialiser handles a specific type or family of types.
    The ``SerializerRegistry`` maps runtime types to the appropriate
    serialiser instance.
    """

    @abstractmethod
    def serialise(self, value: Any) -> bytes:
        """Convert *value* to a byte string.

        Raises
        ------
        SerialiserError
            If *value* cannot be serialised by this serialiser.
        """

    @abstractmethod
    def deserialise(self, data: bytes, type_name: str) -> Any:
        """Reconstruct a value from *data*.

        Parameters
        ----------
        data:
            Raw bytes produced by a prior call to :meth:`serialise`.
        type_name:
            Fully-qualified class name stored in the
            :class:`~pirn.core.transport.transport_handle.TransportHandle`.
            Used when a single serialiser handles multiple types.

        Raises
        ------
        SerialiserError
            If *data* cannot be deserialised.
        """

    @abstractmethod
    def can_handle(self, value: Any) -> bool:
        """Return True if this serialiser can serialise *value*."""
