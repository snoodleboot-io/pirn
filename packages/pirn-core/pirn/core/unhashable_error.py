"""``UnhashableError`` — internal sentinel raised by ``ContentHasher`` to bail on opaque values."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class UnhashableError(PirnError):
    """Internal sentinel used by ``ContentHasher._canonicalise`` to bail on opaque values.

    Carries the offending leaf's type name so ``ContentHasher.hash(...,
    strict=True)`` can name the specific innermost value that defeated
    canonicalisation, rather than only the top-level argument's type (all the
    non-strict ``sha256:unhashable:<type>`` sentinel records). Raised once, at
    the leaf, and left to propagate unchanged up through the recursive
    ``_canonicalise`` calls — nothing between the raise site and
    ``ContentHasher.hash``'s ``except`` catches and re-raises it — so
    ``type_name`` always reflects the leaf, never an ancestor container.
    """

    sentinel = "unhashable"

    def __init__(self, *, type_name: str) -> None:
        """Record the offending leaf's type name.

        Args:
            type_name: ``type(value).__name__`` of the leaf that could not be
                canonicalised.
        """
        self.type_name = type_name
        super().__init__(type_name)
