"""Raised by ``ContentHasher.hash(value, strict=True)`` when a leaf has no canonical form."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class UnhashableValueError(PirnError, TypeError):
    """A value could not be reduced to a canonical, content-addressable form.

    :meth:`~pirn.core.content_hasher.ContentHasher.hash` is best-effort by default: an
    opaque leaf (no ``__pirn_canonical__``, no pydantic core schema, not a
    container the canonicaliser recurses into) degrades to a
    ``sha256:unhashable:<type>`` sentinel rather than raising, because most
    callers only need *a* stable-looking key and would rather get one than
    crash. A caller for whom that degraded key would be actively wrong — two
    distinct un-encodable payloads silently sharing one key, for instance —
    passes ``strict=True`` and gets this exception instead, naming the
    specific innermost value that defeated canonicalisation (not just the
    top-level argument's type, which is all the sentinel form records).

    Subclasses ``TypeError`` in addition to ``PirnError`` so a caller
    migrating from a hand-rolled ``TypeError`` on the same failure mode (see
    the former ``pirn_agents.caching.content_address.ContentAddress``,
    deleted PIR-864, whose own "cannot canonically encode
    a value of type X" refusal this class replaced) keeps its existing
    ``except TypeError`` working unchanged.

    Attributes:
        type_name: The class name of the innermost value that could not be
            canonicalised.
    """

    def __init__(self, *, type_name: str) -> None:
        """Describe an unhashable leaf in terms the caller can act on.

        Args:
            type_name: ``type(value).__name__`` of the offending leaf.
        """
        self._type_name = type_name
        super().__init__(
            f"content_hash: cannot canonically hash a value of type {type_name!r}; "
            f"it has no __pirn_canonical__() hook, no pydantic core schema, and is "
            f"not a container this hasher recurses into. Give the type one of those, "
            f"convert it to a JSON-encodable value first, or pass strict=False to "
            f"receive a 'sha256:unhashable:<type>' sentinel instead of this error."
        )

    @property
    def type_name(self) -> str:
        """The class name of the innermost value that could not be canonicalised."""
        return self._type_name
