"""``MemoryKind`` — the closed set of typed memory-record categories.

A memory record is one of four kinds mirroring ``memory_patterns/``:
``episodic`` (raw conversational episodes), ``semantic`` (distilled facts),
``procedural`` (how-to / skills), and ``profile`` (durable per-user/entity
state). The set is expressed as a :data:`typing.Literal` alias so it stays a
type — not a runtime constant table — and membership is checked with
:meth:`~pirn_agents.memory.management.memory_kind_guard.MemoryKindGuard.is_kind`,
which narrows an arbitrary object to ``MemoryKind`` for pyright-strict
validation at knot boundaries.
"""

from __future__ import annotations

from typing import Literal

MemoryKind = Literal["episodic", "semantic", "procedural", "profile"]
