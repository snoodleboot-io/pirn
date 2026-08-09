"""``OpaquePolicy`` — what canonical encoding does with a non-JSON leaf."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any


class OpaquePolicy(Enum):
    """How :class:`~pirn_agents.serialization.canonical_json.CanonicalJson`
    handles a value the JSON encoder cannot represent.

    This is the only axis on which callers legitimately differ, so it is an
    explicit argument rather than a ``json.dumps`` flag buried in each call
    site.

    Members:
        RAISE: Refuse to encode. The default, and the right choice for any
            digest used as a cache key or a persisted id: a value JSON cannot
            represent has no content-derived encoding, so any fallback invents
            one. Better a loud ``TypeError`` at the boundary than a key that
            silently means the wrong thing.
        REPR: Fall back to :func:`repr`. **Unsafe for cache keys.** The default
            ``object.__repr__`` embeds the instance's memory address, so the
            digest keys on identity rather than content — and because CPython
            reuses freed addresses, two unrelated objects routinely produce the
            same key (PIR-785). Only sound when every opaque leaf is known to
            define a content-derived ``__repr__``.
        STR: Fall back to :func:`str`. Carries the same identity-keying hazard
            as ``REPR`` for types that do not override ``__str__``, since the
            default ``__str__`` delegates to ``__repr__``.
    """

    RAISE = "raise"
    REPR = "repr"
    STR = "str"

    def fallback(self) -> Callable[[Any], str]:
        """Return the ``json.dumps`` ``default=`` hook implementing this policy.

        Returns:
            A callable applied to each leaf the encoder cannot represent. For
            ``RAISE`` the callable raises :class:`TypeError` rather than
            returning a substitute.
        """
        if self is OpaquePolicy.REPR:
            return repr
        if self is OpaquePolicy.STR:
            return str
        return self._refuse

    @staticmethod
    def _refuse(value: Any) -> str:
        """Reject a leaf JSON cannot encode, naming the type that caused it.

        Raises:
            TypeError: Always.
        """
        raise TypeError(
            f"CanonicalJson: cannot canonically encode a value of type "
            f"{type(value).__name__}; JSON has no representation for it, so any "
            f"digest over it would key on the object rather than its content. "
            f"Convert it to a JSON-encodable value first, or pass an explicit "
            f"OpaquePolicy if an identity-keyed digest is genuinely intended."
        )
