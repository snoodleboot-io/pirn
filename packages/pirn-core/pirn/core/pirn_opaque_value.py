"""``PirnOpaqueValue`` — mixin for pydantic-opaque pirn types.

Many pirn types wrap engine-specific or non-pydantic-compatible state
(database connection pools, broker clients, lazy DataFrames, frozen
dataclasses with ``type`` objects in fields, etc.). Pydantic IO
validation between knots needs only an ``isinstance`` check on the
boundary; descending into the underlying state is at best wasteful and
at worst impossible (live engines, lazy plans, ``Mapping[str, type]``).

Before this mixin existed, every such type carried its own copy of::

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return core_schema.is_instance_schema(
            cls,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: ...,
                when_used="always",
            ),
        )

This mixin centralises that body. Subclasses override
:meth:`_pirn_audit_dict` to control what primitive form pydantic emits
when the value is serialised. The default returns an identity-keyed
token (``<TypeName@identity_token>``, see :meth:`_pirn_identity_token`)
suitable for stateful connectors. Frozen
dataclass wrappers (``DataBatch``, ``DataSchema``,
``SparkExecutionReceipt``) override the method to emit a flat dict of
their lineage-relevant fields.

Subclasses that want NO serialiser at all — e.g. lazy frame wrappers
where even a primitive summary is expensive — can override
:meth:`__get_pydantic_core_schema__` themselves to return a bare
``core_schema.is_instance_schema(cls)``.
"""

from __future__ import annotations

import threading
import uuid
import weakref
from functools import partial
from typing import Any, ClassVar

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from pirn.core.pirn_identity_nonce import PirnIdentityNonce


class PirnOpaqueValue:
    """Mixin that provides an opaque pydantic core schema with a pluggable
    serialiser.

    Subclasses can override :meth:`_pirn_audit_dict` to control what
    primitive form pydantic emits when serialising the value. The
    default is an identity-style token (``<TypeName@identity_token>``)
    suitable for stateful connectors. Frozen-dataclass wrappers should
    override :meth:`_pirn_audit_dict` to emit a primitive dict.

    Subclasses that want no serialiser at all can override
    :meth:`__get_pydantic_core_schema__` themselves.
    """

    #: Live instance tokens, keyed by ``id()``. Each entry holds a weak reference
    #: whose callback removes the entry when the instance is deallocated, which
    #: CPython does before the address can be handed to a new object. So an
    #: entry found under ``id(self)`` whose reference still resolves to ``self``
    #: belongs to ``self``, never to a dead predecessor at the same address.
    _pirn_identity_registry: ClassVar[dict[int, tuple[str, weakref.ref[Any]]]] = {}
    _pirn_identity_lock: ClassVar[threading.Lock] = threading.Lock()

    def _pirn_identity_token(self) -> str:
        """Return a token unique to this instance for the life of the process.

        ``id()`` alone is not an identity: CPython reuses a freed object's
        address, so a new object could inherit a dead one's token and hash
        equal to it, which is a false match on replay (PIR-852). The token is a
        random ``uuid4`` hex, assigned lazily on first read, so subclasses that
        never call ``super().__init__`` still get one. It carries no
        configuration.

        It is not stored in the instance's attributes. A ``copy``, a
        ``deepcopy`` or an unpickled instance is a different object, so it gets
        its own token rather than inheriting the original's. A mutated copy
        therefore cannot pass as the object that was recorded. Instances that
        cannot be weakly referenced follow
        :meth:`_pirn_instance_identity_token` instead.

        Returns:
            A 32-character lowercase hex string, stable for this instance.
        """
        registry = PirnOpaqueValue._pirn_identity_registry
        key = id(self)
        entry = registry.get(key)
        if entry is not None and entry[1]() is self:
            return entry[0]
        try:
            ref = weakref.ref(self, partial(PirnOpaqueValue._pirn_forget_identity, key))
        except TypeError:
            return self._pirn_instance_identity_token()
        candidate = (uuid.uuid4().hex, ref)
        with PirnOpaqueValue._pirn_identity_lock:
            entry = registry.get(key)
            if entry is None or entry[1]() is not self:
                registry[key] = candidate
                entry = candidate
        return entry[0]

    def _pirn_instance_identity_token(self) -> str:
        """Token fallback for an instance that cannot be weakly referenced.

        Only a subclass that also derives from a builtin such as ``tuple``,
        ``int`` or ``bytes`` reaches this. It never compares ``id()``: an
        unpickled object can land at the original's freed address.

        * With an instance ``__dict__`` (every such subclass, since this mixin
          declares no ``__slots__``), the token lives there in a
          :class:`PirnIdentityNonce`. That holder re-mints on ``pickle`` and
          ``copy.deepcopy``, so a rebuilt object gets its own token. A shallow
          ``copy.copy`` shares the instance dict's values and therefore the
          token. That is the one case where a copy keeps identity.
        * Without one, the value refuses: every read returns a fresh token, so
          it never hashes equal to anything, itself included, and replay
          always raises rather than substituting.
        """
        state = getattr(self, "__dict__", None)
        if not isinstance(state, dict):
            return uuid.uuid4().hex
        nonce = state.get("_pirn_identity_nonce")
        if not isinstance(nonce, PirnIdentityNonce):
            nonce = PirnIdentityNonce()
            state["_pirn_identity_nonce"] = nonce
        return nonce.token

    @staticmethod
    def _pirn_forget_identity(key: int, ref: weakref.ref[Any]) -> None:
        """Weakref callback: drop the registry entry of a deallocated instance.

        It only removes the entry that holds this exact reference, so a
        reference discarded by a lost first-read race removes nothing. It takes
        no lock, because it may run inside a garbage collection triggered while
        the lock is held. It cannot race a new entry at ``key``, since the
        address is not reused until this deallocation completes.
        """
        registry = PirnOpaqueValue._pirn_identity_registry
        entry = registry.get(key)
        if entry is not None and entry[1] is ref:
            registry.pop(key, None)

    def _pirn_audit_dict(self) -> Any:
        """Return the primitive form pydantic emits for this value.

        Default: an identity-keyed token, ``<TypeName@identity_token>``, built
        from :meth:`_pirn_identity_token` so a reused address never repeats a
        token. Wrapper dataclasses override to emit a flat dict of their
        lineage-relevant fields.
        """
        return f"<{type(self).__name__}@{self._pirn_identity_token()}>"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Tell pydantic to treat the value as opaque.

        Pirn IO validation only needs ``isinstance(value, cls)``; this
        short-circuit avoids pydantic descending into engine internals,
        ``type`` objects, lazy plans, or other non-JSON-serialisable
        members. The serialiser delegates to :meth:`_pirn_audit_dict`
        so subclasses control the emitted form without re-stating the
        schema-construction boilerplate.
        """
        return core_schema.is_instance_schema(
            cls,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: v._pirn_audit_dict(),
                when_used="always",
            ),
        )
