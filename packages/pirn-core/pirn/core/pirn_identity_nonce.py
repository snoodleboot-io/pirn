"""``PirnIdentityNonce`` — a per-instance identity token that does not survive a copy.

:class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` keys most instances'
identity tokens on a weak reference. An instance that cannot be weakly
referenced (a subclass that also derives from ``tuple``, ``int`` or ``bytes``)
keeps its token in its own ``__dict__`` instead, wrapped in this holder.

Anything in ``__dict__`` travels with a copy, and a bare token would travel
with it, so the copy, mutated or not, would hash equal to the original. The
holder closes both routes:

* It reduces to a fresh, ownerless instance, so ``pickle`` and
  ``copy.deepcopy`` never carry the token.
* It records the ``id()`` of the instance it was minted for. ``copy.copy``
  shares ``__dict__`` values, so the copy sees the original's holder. The copy
  necessarily lives at a different address from its still-live original, so
  the owner check fails and the copy mints its own. An owner-id match cannot be
  forged by address reuse either: a reused address belongs to a new object
  whose ``__dict__`` never held this holder, except through pickle, which
  already dropped the owner.
"""

from __future__ import annotations

import uuid
from typing import Any


class PirnIdentityNonce:
    """A random token bound to the ``id()`` of the instance it was minted for."""

    __slots__ = ("owner_id", "token")

    def __init__(self, owner_id: int | None = None) -> None:
        """Mint a new random ``uuid4`` hex token for ``owner_id``.

        Args:
            owner_id: ``id()`` of the owning instance, or ``None`` for a holder
                rebuilt by pickle or deepcopy, which no instance owns yet.
        """
        self.owner_id: int | None = owner_id
        self.token: str = uuid.uuid4().hex

    def is_owned_by(self, instance: object) -> bool:
        """Whether this holder was minted for ``instance``."""
        return self.owner_id is not None and self.owner_id == id(instance)

    def __reduce__(self) -> tuple[Any, tuple[()]]:
        """Rebuild as a brand-new, ownerless nonce, so a pickle or deepcopy gets its own token."""
        return (PirnIdentityNonce, ())
