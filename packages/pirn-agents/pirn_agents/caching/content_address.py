"""Content-addressed cache keying: a stable hash over an arbitrary payload.

.. deprecated::
    ADR agents-speaks-core WS2 part 2: delegates to
    :func:`pirn.core.hashing.content_hash` (``strict=True``) now that core
    has a strict mode. **New call sites must call** ``content_hash(value,
    strict=True)`` **directly and must not use this class.**

Mirrors how the DAG content-addresses node outputs — two calls with identical
inputs hash to the same key, so an idempotent tool call or embedding lookup
maps deterministically onto a cache entry. Keys are order-independent because
mappings are serialised with sorted keys.

WS2 part 1 deferred this migration: :func:`content_hash`'s *default* mode is
best-effort — an opaque leaf degrades to a ``sha256:unhashable:<outer-type>``
sentinel that does not vary with the leaf's content, only the top-level
payload's Python type, and this class exists specifically to prevent that
exact collision (PIR-785). ``strict=True`` (WS2 part 2) closes that gap: it
raises :class:`~pirn.exceptions.unhashable_value_error.UnhashableValueError`
naming the *innermost* offending type instead of degrading, which is at
least as precise as the ``OpaquePolicy``-driven ``TypeError`` this class
raised before — see ``test_the_raise_names_the_offending_type``. Note the
key format changed alongside the algorithm: ``content_hash`` returns the
``sha256:``-prefixed form, not the bare 64-hex digest this class returned
before. Every caller of ``ContentAddress``/``content_address`` is an
in-memory-only cache key (``ResultCache``, ``PromptCache``, ``EmbeddingCache``,
``SemanticResultCache``) with nothing persisted across a process restart, so
the format change carries no migration risk.
"""

from __future__ import annotations

import warnings
from typing import Any

from pirn.core.hashing import content_hash


class ContentAddress:
    """Namespace for content-addressed cache keying.

    .. deprecated::
        See the module docstring. Call :func:`pirn.core.hashing.content_hash`
        directly instead.
    """

    @staticmethod
    def digest(payload: Any) -> str:
        """Return a stable, content-addressed key for ``payload``.

        Args:
            payload: A JSON-encodable value (mappings, sequences, scalars).

        Returns:
            :func:`~pirn.core.hashing.content_hash`'s ``sha256:``-prefixed
            digest — identical for equal payloads, order-independent across
            mapping keys.

        Raises:
            UnhashableValueError: If ``payload`` contains a value with no
                canonical form (naming the innermost offending type). Also a
                ``TypeError``, so an existing ``except TypeError`` around
                this call keeps working. This used to fall back to ``repr``
                so the keyer "never raised on live objects" (PIR-785). That
                was worse than raising: the default ``object.__repr__`` is
                built from the instance's memory address, so the key
                described *where the object sat*, not what it contained —
                and CPython hands a freed address straight back to the next
                allocation. Two hundred distinct requests collapsed onto
                seventeen keys, and
                :meth:`~pirn_agents.caching.result_cache.ResultCache.get_or_compute`
                answered one request with another's value, silently.
                Callers with a non-JSON payload must project it to
                JSON-encodable data first, so the key is derived from
                content the caller chose.
        """
        warnings.warn(
            "ContentAddress.digest is deprecated (ADR agents-speaks-core WS2); "
            "call pirn.core.hashing.content_hash(payload, strict=True) directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        return content_hash(payload, strict=True)


def content_address(payload: Any) -> str:
    """Return a stable, content-addressed key for ``payload``.

    .. deprecated::
        Call :func:`pirn.core.hashing.content_hash` (``strict=True``)
        directly. Kept for the documented public import path (see
        ``PATTERNS.md``) for one deprecation cycle; see
        :meth:`ContentAddress.digest`, which this delegates to (so a single
        call emits exactly one deprecation warning).
    """
    return ContentAddress.digest(payload)
