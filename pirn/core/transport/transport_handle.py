"""``TransportHandle`` — lightweight token representing a knot output in a transport backend.

The executor caches handles, never raw values. A handle is always small
regardless of the size of the data it references. Concrete transports
embed or reference the actual data via whichever storage backend they
wrap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TransportHandle:
    """Opaque token produced by a transport write and consumed by a transport read.

    Fields
    ------
    transport_id:
        Identifies which transport instance produced this handle so the
        executor can route reads back to the correct backend.
    key:
        Location or identity of the stored value within the backend
        (e.g. a filesystem path, an object-store key, a Redis key, or
        an empty string for inline handles where ``_inline_value`` holds
        the data directly).
    type_name:
        Fully-qualified class name of the stored value, used by the
        deserialiser to reconstruct the correct type.
    size_bytes:
        Estimated serialised size in bytes. Zero for inline handles.
        Used for observability and size-guard warnings.
    checksum:
        Hex digest of the serialised bytes, or empty string when the
        backend does not compute one (inline transport).
    _inline_value:
        Only populated by ``InlineTransport``. Holds the actual Python
        object so that inline transport imposes no serialisation overhead.
        All other transports leave this as ``None``.
    """

    transport_id: str
    key: str
    type_name: str
    size_bytes: int = 0
    checksum: str = ""
    _inline_value: Any = field(default=None, compare=False, hash=False)
