# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``MemoryContent`` — the domain-data half of a memory ``Payload``.

ADR "agents speaks core" WS3 makes
:class:`~pirn_agents.memory.management.memory_record.MemoryRecord` a
``pirn.core.payload.Payload[MemoryProvenance, MemoryContent]``: the frame
(``MemoryProvenance``) carries source, trust, and lifecycle timestamps; this
class is the ``D`` — the stable id, kind, text content, and free-form tags a
writer knot actually produced. Splitting the two lets generic code program
against ``.metadata`` / ``.data`` (the ``Payload`` contract every domain
follows — see ``pirn_signal.types.signal_payload.SignalPayload``) while
``MemoryRecord`` keeps its existing domain-readable aliases (``.id``,
``.kind``, ``.content``, ...) for every current caller.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.memory.management.memory_kind import MemoryKind
from pirn_agents.memory.management.memory_kind_guard import MemoryKindGuard


@dataclass(frozen=True)
class MemoryContent(PirnOpaqueValue):
    """A memory record's stable id, kind, text content, and free-form tags.

    Attributes
    ----------
    id:
        Stable primary key; the store key the record is (or was) persisted
        under, and the join key eviction and recall use.
    kind:
        The record's :data:`~pirn_agents.memory.management.memory_kind.MemoryKind`.
    content:
        The record's text payload.
    tags:
        Arbitrary scalar metadata (e.g. ``session_id``, subject keys). Named
        ``tags`` (not ``metadata``) so it does not collide with
        ``Payload.metadata``, which on ``MemoryRecord`` is the
        ``MemoryProvenance`` frame.
    """

    id: str
    kind: MemoryKind
    content: str
    tags: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise TypeError("MemoryContent: id must be a non-empty str")
        if not MemoryKindGuard.is_kind(self.kind):
            raise ValueError(f"MemoryContent: kind must be a MemoryKind, got {self.kind!r}")
        if not isinstance(self.content, str):
            raise TypeError(
                f"MemoryContent: content must be a str, got {type(self.content).__name__}"
            )
        if not isinstance(self.tags, Mapping):
            raise TypeError(
                f"MemoryContent: tags must be a Mapping, got {type(self.tags).__name__}"
            )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "content": self.content, "tags": dict(self.tags)}
