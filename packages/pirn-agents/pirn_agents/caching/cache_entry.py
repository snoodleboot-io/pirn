"""``CacheEntry`` — one stored value plus its content-address key and optional embedding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class CacheEntry(PirnOpaqueValue):
    """A cached value keyed by content address, optionally carrying its embedding.

    Attributes
    ----------
    key:
        The content-address key the entry is stored under.
    value:
        The cached payload (an embedding vector, a tool result, etc.). May be
        any python object.
    embedding:
        The vector used for semantic matching, or ``None`` for exact-key-only
        entries. Held as a tuple so the frozen entry stays hashable.
    """

    key: str
    value: Any
    embedding: tuple[float, ...] | None = None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": repr(self.value),
            "embedding": None if self.embedding is None else list(self.embedding),
        }
