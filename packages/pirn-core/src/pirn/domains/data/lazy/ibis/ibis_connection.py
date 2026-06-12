"""``IbisConnection`` — pydantic-opaque wrapper for an Ibis backend connection.

An Ibis backend connection is a live, engine-backed object that pydantic
cannot introspect or serialise. This thin wrapper inherits
:class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` so it receives an
opaque ``isinstance`` schema, allowing it to travel between Knots in the
pirn graph without triggering pydantic schema generation errors.

The wrapped backend is accessed via the read-only :attr:`backend` property.
"""

from __future__ import annotations

from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class IbisConnection(PirnOpaqueValue):
    """Pydantic-opaque holder for an Ibis backend connection.

    Pass this through the pirn graph and unwrap with ``.backend`` in any
    consuming Knot's ``process()`` method.
    """

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    @property
    def backend(self) -> Any:
        return self._backend

    def _pirn_audit_dict(self) -> Any:
        return f"<IbisConnection@{id(self._backend):x}>"
