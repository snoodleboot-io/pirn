"""``PirnIdentityNonce`` — a per-instance identity token that does not survive a copy.

:class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` keys most instances'
identity tokens on a weak reference. An instance that cannot be weakly
referenced (a subclass that also derives from ``tuple``, ``int`` or ``bytes``)
keeps its token in its own ``__dict__`` instead, wrapped in this holder.

Anything in ``__dict__`` travels with ``pickle`` and ``copy.deepcopy``, and a
bare string token would travel with it. The rebuilt object would then hash
equal to the original, and so would a mutated copy. This holder reduces to a
fresh instance, so pickling or deep-copying it mints a new token. It never
compares addresses.
"""

from __future__ import annotations

import uuid
from typing import Any


class PirnIdentityNonce:
    """A random token that is re-minted, not copied, on pickle and deepcopy."""

    __slots__ = ("token",)

    def __init__(self) -> None:
        """Mint a new random ``uuid4`` hex token."""
        self.token: str = uuid.uuid4().hex

    def __reduce__(self) -> tuple[Any, tuple[()]]:
        """Rebuild as a brand-new nonce, so a pickle or deepcopy gets its own token."""
        return (PirnIdentityNonce, ())
