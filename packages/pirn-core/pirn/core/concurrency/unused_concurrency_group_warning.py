"""Warns that a limited concurrency group matches no knot of the run."""

from __future__ import annotations


class UnusedConcurrencyGroupWarning(UserWarning):
    """A group defined in ``ConcurrencyLimits.groups`` matches no knot.

    Emitted at run start, checked against the static graph.  It is a warning,
    not an error, because knots registered mid-run may still join the group,
    but it usually means the limits and the graph disagree on a name, so the
    cap is not applied where it was meant to be.
    """
