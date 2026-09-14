"""``TrajectoryCallKey`` — stable, order-independent key for a step's arguments."""

from __future__ import annotations

from pirn.core.hashing import content_hash


class TrajectoryCallKey:
    """Build a stable content key from a trajectory step's arguments.

    The key is only ever compared with another key from the same process —
    :class:`~pirn_agents.evaluation.redundant_call_rate.RedundantCallRate` puts
    it in a local ``set`` and
    :class:`~pirn_agents.evaluation.tool_choice_accuracy.ToolChoiceAccuracy`
    compares two of them inline. Nothing persists it, so the encoding is free to
    change; what is *not* free is the key failing to be stable, because both
    callers read equality as "the same call was made twice" / "the agent called
    what was expected".

    **Stability is the whole contract, so it is enforced rather than hoped for**
    (PIR-826). The key is core's :func:`pirn.core.hashing.content_hash` in
    ``strict`` mode: an argument with no canonical form (one that would only
    render as ``<Foo object at 0x...>``) raises instead of producing a key that
    differs between two structurally identical calls.

    Raising is the right answer *here*: these are measurements, and a metric
    that quietly reports a wrong score is worse than one that declines to score.
    """

    def args_key(self, arguments: object) -> str:
        """Return a stable, order-independent key for a step's arguments.

        Args:
            arguments: The step's arguments, normally a mapping. Mapping keys
                are sorted before hashing, so the result is independent of
                mapping order.

        Returns:
            The ``sha256:``-prefixed content hash of ``arguments``.

        Raises:
            UnhashableValueError: If ``arguments`` contains a leaf with no
                canonical form (a ``TypeError`` subclass), which could not
                yield a stable key.
        """
        return content_hash(arguments, strict=True)
