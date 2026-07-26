"""``MemoryKind`` — the closed set of typed memory-record categories.

A memory record is one of four kinds mirroring ``memory_patterns/``:
``episodic`` (raw conversational episodes), ``semantic`` (distilled facts),
``procedural`` (how-to / skills), and ``profile`` (durable per-user/entity
state). The set is expressed as a :data:`typing.Literal` alias so it stays a
type — not a runtime constant table — and membership is checked with
:func:`is_memory_kind`, which narrows an arbitrary object to ``MemoryKind`` for
pyright-strict validation at knot boundaries.
"""

from __future__ import annotations

from typing import Literal, TypeGuard, get_args

MemoryKind = Literal["episodic", "semantic", "procedural", "profile"]


def is_memory_kind(value: object) -> TypeGuard[MemoryKind]:
    """Return ``True`` when ``value`` is one of the four memory kinds.

    Args:
        value: Any object; only the exact kind strings pass.

    Returns:
        ``True`` if ``value`` is a valid :data:`MemoryKind`, narrowing its type.
    """
    return isinstance(value, str) and value in get_args(MemoryKind)
