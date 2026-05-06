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
token (``<TypeName@hex_id>``) suitable for stateful connectors. Frozen
dataclass wrappers (``DataBatch``, ``DataSchema``,
``SparkExecutionReceipt``) override the method to emit a flat dict of
their lineage-relevant fields.

Subclasses that want NO serialiser at all — e.g. lazy frame wrappers
where even a primitive summary is expensive — can override
:meth:`__get_pydantic_core_schema__` themselves to return a bare
``core_schema.is_instance_schema(cls)``.
"""

from __future__ import annotations

from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class PirnOpaqueValue:
    """Mixin that provides an opaque pydantic core schema with a pluggable
    serialiser.

    Subclasses can override :meth:`_pirn_audit_dict` to control what
    primitive form pydantic emits when serialising the value. The
    default is an identity-style token (``<TypeName@hex_id>``) suitable
    for stateful connectors. Frozen-dataclass wrappers should override
    :meth:`_pirn_audit_dict` to emit a primitive dict.

    Subclasses that want no serialiser at all can override
    :meth:`__get_pydantic_core_schema__` themselves.
    """

    def _pirn_audit_dict(self) -> Any:
        """Return the primitive form pydantic emits for this value.

        Default: an identity-keyed token. Wrapper dataclasses override
        to emit a flat dict of their lineage-relevant fields.
        """
        return f"<{type(self).__name__}@{id(self):x}>"

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
