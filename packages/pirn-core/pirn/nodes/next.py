"""``Next`` — one successor descriptor returned by a continuation function."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Next:
    """One successor to spawn from a continuation.

    ``action`` maps to a knot class in the pool.  ``inputs`` are passed as
    constructor kwargs — plain values become config constants, ``Knot``
    instances become parent edges exactly as in any pirn constructor.

    ``id`` overrides the auto-generated knot id.  Leave it ``None`` to get
    a stable derived id (``"{continuation_id}_{action}_{index}"``).
    """

    action: str
    inputs: dict[str, Any] = field(default_factory=dict)
    id: str | None = None
