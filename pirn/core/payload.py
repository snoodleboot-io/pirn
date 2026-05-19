"""``Payload`` — generic base class for all pirn domain payload types.

Every payload carries two things together through the transport layer:

- **metadata** — a typed descriptor (``SignalFrame``, ``LASFile``, etc.)
  that provides provenance, lineage, and structural context.
- **data** — the actual computation result (numpy arrays, fitted models,
  metric dicts, etc.).

Concrete subclasses expose domain-readable aliases for the two slots
(e.g. ``series`` / ``values`` on ``ScadaPayload``) as read-only
properties backed by ``_metadata`` / ``_data``.  Generic code programs
against ``.metadata`` / ``.data``; domain knots use the semantic names.

Serialisation
-------------
``_pirn_audit_dict`` delegates entirely to ``metadata._pirn_audit_dict()``.
The metadata type is responsible for describing itself; the payload adds
no extra keys so the audit trail stays in one place.

Transport round-trips use pickle (via ``PickleSerializer`` fallback in
``SerializerRegistry``).  The audit dict is never used for reconstruction.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pirn.core.pirn_opaque_value import PirnOpaqueValue

M = TypeVar("M")
D = TypeVar("D")


class Payload(PirnOpaqueValue, Generic[M, D]):
    """Base class for all pirn payload types.

    Parameters
    ----------
    metadata:
        Typed metadata descriptor for this payload.
    data:
        The actual data carried by this payload.
    """

    def __init__(self, metadata: M, data: D) -> None:
        self._metadata = metadata
        self._data = data

    @property
    def metadata(self) -> M:
        return self._metadata

    @property
    def data(self) -> D:
        return self._data

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self._metadata._pirn_audit_dict()  # type: ignore[union-attr]

    def __repr__(self) -> str:
        return f"{type(self).__name__}(metadata={self._metadata!r})"
