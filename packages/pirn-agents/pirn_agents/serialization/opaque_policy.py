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
        REPR_CONTENT: Fall back to :func:`repr`, but refuse any leaf whose
            ``repr`` is the default ``<X object at 0x...>`` form. This is
            ``REPR`` with the PIR-785 hazard removed and nothing else changed:
            a leaf that already rendered content — ``datetime``, ``UUID``,
            ``Decimal``, ``Path``, an ``Enum``, or any type defining its own
            ``__repr__`` — encodes byte-identically to ``REPR``, so no digest
            that was stable moves. Only the leaves that were *silently* keying
            on a memory address now raise.
        STR_CONTENT: The same narrowing applied to ``STR``. Kept separate from
            ``REPR_CONTENT`` because ``str`` and ``repr`` disagree on exactly
            the types this is meant to keep working — ``str(Decimal("1.25"))``
            is ``1.25`` where ``repr`` is ``Decimal('1.25')`` — so collapsing
            the two would move every digest they are meant to preserve.

    ``*_CONTENT`` are the sound choice for a digest that must survive a retry
    or a replay. ``RAISE`` is stricter still, but it also rejects the
    content-rendering leaves above, so tightening an existing key space to it
    is a migration; tightening to ``*_CONTENT`` is not (PIR-795).
    """

    RAISE = "raise"
    REPR = "repr"
    STR = "str"
    REPR_CONTENT = "repr_content"
    STR_CONTENT = "str_content"

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
        if self is OpaquePolicy.REPR_CONTENT:
            return self._content_only(repr)
        if self is OpaquePolicy.STR_CONTENT:
            return self._content_only(str)
        return self._refuse

    @staticmethod
    def _content_only(render: Callable[[Any], str]) -> Callable[[Any], str]:
        """Wrap ``render`` so it refuses leaves that render their own identity.

        The test is whether ``render`` produced exactly what
        ``object.__repr__`` would have — the ``<X object at 0x7f...>`` form.
        That is precisely the case in which the digest keys on a memory address
        instead of content, and it is the only case ``*_CONTENT`` rejects.

        Comparing the *rendered* text, rather than checking
        ``type(value).__repr__ is object.__repr__``, is what makes this correct
        for both fallbacks at once. A class that defines ``__str__`` but not
        ``__repr__`` renders content under ``str`` and identity under ``repr``;
        testing the output judges each fallback on what it actually encoded.

        Args:
            render: The underlying fallback, :func:`repr` or :func:`str`.

        Returns:
            A fallback with the same output as ``render`` for every leaf it
            accepts, so digests taken with the un-narrowed policy do not move.
        """

        def _render_content(value: Any) -> str:
            rendered = render(value)
            try:
                identity = object.__repr__(value)
            except Exception:  # pragma: no cover - defensive; see below
                # Not reachable by construction as far as we can build:
                # `object.__repr__` reads the type's __module__/__qualname__
                # slots at C level, so even a metaclass overriding
                # __getattribute__ does not make it raise. Kept as depth, and
                # deliberately routed through the GENERIC refusal — calling
                # _refuse_identity here would re-enter the very call that just
                # failed and let that error escape in place of the TypeError
                # callers are documented to get.
                return OpaquePolicy._refuse(value)
            if rendered == identity:
                return OpaquePolicy._refuse_identity(value, identity)
            return rendered

        return _render_content

    @staticmethod
    def _refuse_identity(value: Any, identity: str) -> str:
        """Reject a leaf that renders as its own identity rather than content.

        Distinct from :meth:`_refuse` because the cause is different and so is
        the remedy: the value *did* render, it simply rendered a memory address.
        Saying so is the point of the policy — this error is what turns a wrong
        answer discovered at replay or retry time into a loud one at record or
        issue time.

        Args:
            value: The leaf being refused.
            identity: Its already-computed ``object.__repr__``. Passed in rather
                than recomputed so this never re-enters a call the caller has
                already made — and so it cannot raise something other than the
                documented :class:`TypeError`.

        Raises:
            TypeError: Always.
        """
        raise TypeError(
            f"CanonicalJson: refusing to digest a value of type "
            f"{type(value).__name__}; it renders as {identity!r}, "
            f"which is its memory address rather than its content. A digest over "
            f"it would differ on the very next run — so a cassette keyed by it "
            f"could never replay, and an idempotency key derived from it would "
            f"change on the retry it exists to deduplicate. Give the type a "
            f"content-derived __repr__/__str__, convert it to a JSON-encodable "
            f"value first, or pass OpaquePolicy.REPR/STR if an identity-keyed "
            f"digest is genuinely intended."
        )

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
