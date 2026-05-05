"""``DatafusionSessionContext`` — pydantic-opaque wrapper for :class:`datafusion.SessionContext`.

:class:`datafusion.SessionContext` is a Rust-backed native object that pydantic
cannot introspect or serialise. This thin wrapper inherits
:class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` so it receives an opaque
``isinstance`` schema, allowing it to travel between Knots in the pirn graph
without triggering pydantic schema generation errors.

The wrapped context is accessed via the read-only :attr:`ctx` property.
"""

from __future__ import annotations

from typing import Any

import datafusion as df

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class DatafusionSessionContext(PirnOpaqueValue):
    """Pydantic-opaque holder for a :class:`datafusion.SessionContext`.

    Pass this through the pirn graph and unwrap with ``.ctx`` in any
    consuming Knot's ``process()`` method.
    """

    def __init__(self, ctx: df.SessionContext) -> None:
        self._ctx = ctx

    @property
    def ctx(self) -> df.SessionContext:
        return self._ctx

    def _pirn_audit_dict(self) -> Any:
        return f"<DatafusionSessionContext@{id(self._ctx):x}>"
