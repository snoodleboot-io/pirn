"""``MemoryKindGuard`` — runtime membership check for :data:`MemoryKind`.

Split out of ``memory_kind.py`` (which holds only the :data:`MemoryKind`
:data:`typing.Literal` alias) so each file defines at most one class.
"""

from __future__ import annotations

from typing import TypeGuard, get_args

from pirn_agents.memory.management.memory_kind import MemoryKind


class MemoryKindGuard:
    """Namespace for the :data:`MemoryKind` membership :class:`TypeGuard`."""

    @staticmethod
    def is_kind(value: object) -> TypeGuard[MemoryKind]:
        """Return ``True`` when ``value`` is one of the four memory kinds.

        Args:
            value: Any object; only the exact kind strings pass.

        Returns:
            ``True`` if ``value`` is a valid :data:`MemoryKind`, narrowing its type.
        """
        return isinstance(value, str) and value in get_args(MemoryKind)
