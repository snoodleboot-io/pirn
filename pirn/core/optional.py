"""Optional mixin for Knot subclasses."""

from __future__ import annotations


class Optional:
    """Mixin: a knot whose failure or skip propagates as ``Skipped`` to
    children rather than as ``Err``.

    Children using ``SKIP_IF_PARENT_FAILED`` still skip; children using
    ``REQUIRE_ALL_PARENTS`` still fail synthetically; but the distinction
    matters for visualisations, status reporting, and ``RECEIVE_ERRORS``
    knots that want to detect "the parent opted out" vs "the parent
    crashed".

    Use as a mixin on a Knot subclass::

        class FetchPrefs(Optional, Knot):
            async def process(self, user_id: str) -> dict:
                ...
    """
