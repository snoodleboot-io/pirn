"""``SerializerRegistry`` — maps value types to the serialiser that handles them.

Concrete transports delegate type-aware serialisation here rather than
hard-coding type checks. The registry walks the MRO of a value's type
so subclasses inherit their parent's registration. Registrations are
ordered; the first match wins.

The :class:`~pirn.core.transport.serializers.pickle_serializer.PickleSerializer`
is the catch-all fallback that handles every type. Because pickle is a
remote-code-execution sink on bytes read back from a store, the registry — not
each call site — owns that fallback and is constructed with the signing
configuration it needs: ``SerializerRegistry(signer=...)`` in production, or
``allow_unsigned=True`` with ``PIRN_ALLOW_UNSIGNED=1`` for a single-tenant dev
or test environment (PIR-873). ``get`` and ``get_by_type_name`` hand back that
one configured instance rather than building a fresh unsigned one.

Optional serialisers for numpy arrays are registered automatically when the
corresponding library is importable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pirn.core.transport.serializers.pickle_serializer import PickleSerializer
from pirn.core.transport.serializers.serializer import Serializer

if TYPE_CHECKING:
    from pirn.backends.signer import Signer


class SerializerRegistry:
    """Thread-safe (read-heavy) registry mapping types to serialisers.

    Usage
    -----
    >>> registry = SerializerRegistry.default(signer=Signer.from_env())
    >>> ser = registry.get(my_value)
    >>> raw = ser.serialise(my_value)
    >>> original = ser.deserialise(raw, type(my_value).__qualname__)
    """

    def __init__(self, *, signer: Signer | None = None, allow_unsigned: bool = False) -> None:
        """Build an empty registry over a configured pickle fallback.

        Args:
            signer: Forwarded to the
                :class:`~pirn.core.transport.serializers.pickle_serializer.PickleSerializer`
                fallback, which signs on write and verifies on read.
            allow_unsigned: Forwarded to the same fallback; requires
                ``PIRN_ALLOW_UNSIGNED=1``.

        Raises:
            ValueError: If the fallback is neither signed nor explicitly
                acknowledged as unsigned.
        """
        self._entries: list[tuple[type, Serializer]] = []
        self._fallback: Serializer = PickleSerializer(signer=signer, allow_unsigned=allow_unsigned)

    def register(self, handled_type: type, serialiser: Serializer) -> None:
        """Register *serialiser* as the handler for *handled_type* and its subclasses.

        Registrations are prepended so later calls take priority over
        earlier ones (last-registered-wins for the same type).
        """
        self._entries.insert(0, (handled_type, serialiser))

    def get(self, value: object) -> Serializer:
        """Return the most specific registered serialiser for *value*.

        Falls back to this registry's configured
        :class:`~pirn.core.transport.serializers.pickle_serializer.PickleSerializer`
        if no registration matches.
        """
        value_type = type(value)
        for registered_type, serialiser in self._entries:
            if issubclass(value_type, registered_type) and serialiser.can_handle(value):
                return serialiser
        return self._fallback

    def get_by_type_name(self, type_name: str) -> Serializer:
        """Return a serialiser capable of deserialising *type_name*.

        Iterates registrations in priority order and returns the first
        whose registered type's qualified name matches *type_name*.
        Falls back to this registry's configured
        :class:`~pirn.core.transport.serializers.pickle_serializer.PickleSerializer`.
        """
        for registered_type, serialiser in self._entries:
            qualified = f"{registered_type.__module__}.{registered_type.__qualname__}"
            if qualified == type_name or registered_type.__qualname__ == type_name:
                return serialiser
        return self._fallback

    @classmethod
    def default(
        cls, *, signer: Signer | None = None, allow_unsigned: bool = False
    ) -> SerializerRegistry:
        """Return a registry pre-populated with built-in serialisers.

        Optional serialisers are registered only when the corresponding
        library is importable, so callers do not need to install extras
        they do not use.

        Args:
            signer: Forwarded to the pickle fallback.
            allow_unsigned: Forwarded to the pickle fallback; requires
                ``PIRN_ALLOW_UNSIGNED=1``.

        Raises:
            ValueError: If the fallback is neither signed nor explicitly
                acknowledged as unsigned.
        """
        registry = cls(signer=signer, allow_unsigned=allow_unsigned)
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
