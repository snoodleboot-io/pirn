"""``GraphDirection`` — which way a neighbourhood expansion follows edges."""

from __future__ import annotations

from enum import Enum


class GraphDirection(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """The edge orientations a one-hop neighbourhood expansion may follow.

    String-valued for stable, human-readable serialisation independent of enum
    ordering, so callers may keep passing the plain ``"out"`` / ``"in"`` /
    ``"both"`` literals.

    This enum owns the *direction vocabulary* only. How a direction is rendered
    is backend-specific — the Cypher relationship patterns differ between
    adapters — so each backend keeps its own translation and none of it leaks
    into the shared vocabulary.

    Members
    -------
    OUT:
        Follow edges leaving the node.
    IN:
        Follow edges arriving at the node.
    BOTH:
        Follow edges in either orientation; outgoing edges are yielded before
        incoming ones.
    """

    OUT = "out"
    IN = "in"
    BOTH = "both"

    @classmethod
    def parse(cls, direction: str, *, owner: str) -> GraphDirection:
        """Return the member whose value is ``direction``.

        Args:
            direction: The caller-supplied direction.
            owner: The class name to prefix the error with, so a rejection names
                the layer the caller actually invoked.

        Returns:
            The matching :class:`GraphDirection` member.

        Raises:
            ValueError: If ``direction`` is outside the vocabulary.
        """
        for member in cls:
            if member.value == direction:
                return member
        allowed = "|".join(f"'{member.value}'" for member in cls)
        raise ValueError(f"{owner}: direction must be {allowed}, got {direction!r}")
