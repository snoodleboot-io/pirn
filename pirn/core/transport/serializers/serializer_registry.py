"""``SerializerRegistry`` — maps value types to the serialiser that handles them.

Concrete transports delegate type-aware serialisation here rather than
hard-coding type checks. The registry walks the MRO of a value's type
so subclasses inherit their parent's registration. Registrations are
ordered; the first match wins.

The :class:`~pirn.core.transport.serializers.pickle_serializer.PickleSerializer`
is pre-registered as a catch-all fallback that handles every type.
Optional serialisers for numpy arrays, PyArrow tables, and Polars frames
are registered automatically when the corresponding libraries are
importable.
"""

from __future__ import annotations

from typing import Any

from pirn.core.transport.serializers.pickle_serializer import PickleSerializer
from pirn.core.transport.serializers.serializer import Serializer


class SerializerRegistry:
    """Thread-safe (read-heavy) registry mapping types to serialisers.

    Usage
    -----
    >>> registry = SerializerRegistry.default()
    >>> ser = registry.get(my_value)
    >>> raw = ser.serialise(my_value)
    >>> original = ser.deserialise(raw, type(my_value).__qualname__)
    """

    def __init__(self) -> None:
        self._entries: list[tuple[type, Serializer]] = []

    def register(self, handled_type: type, serialiser: Serializer) -> None:
        """Register *serialiser* as the handler for *handled_type* and its subclasses.

        Registrations are prepended so later calls take priority over
        earlier ones (last-registered-wins for the same type).
        """
        self._entries.insert(0, (handled_type, serialiser))

    def get(self, value: Any) -> Serializer:
        """Return the most specific registered serialiser for *value*.

        Falls back to :class:`~pirn.core.transport.serializers.pickle_serializer.PickleSerializer`
        if no registration matches.
        """
        value_type = type(value)
        for registered_type, serialiser in self._entries:
            if issubclass(value_type, registered_type) and serialiser.can_handle(value):
                return serialiser
        return PickleSerializer()

    def get_by_type_name(self, type_name: str) -> Serializer:
        """Return a serialiser capable of deserialising *type_name*.

        Iterates registrations in priority order and returns the first
        whose registered type's qualified name matches *type_name*.
        Falls back to :class:`~pirn.core.transport.serializers.pickle_serializer.PickleSerializer`.
        """
        for registered_type, serialiser in self._entries:
            qualified = f"{registered_type.__module__}.{registered_type.__qualname__}"
            if qualified == type_name or registered_type.__qualname__ == type_name:
                return serialiser
        return PickleSerializer()

    @classmethod
    def default(cls) -> SerializerRegistry:
        """Return a registry pre-populated with built-in serialisers.

        Optional serialisers are registered only when the corresponding
        library is importable, so callers do not need to install extras
        they do not use.
        """
        registry = cls()
        cls._register_numpy(registry)
        return registry

    @staticmethod
    def _register_numpy(registry: SerializerRegistry) -> None:
        try:
            import numpy as np

            from pirn.core.transport.serializers.numpy_serializer import NumpySerializer

            registry.register(np.ndarray, NumpySerializer())
        except ImportError:
            pass
