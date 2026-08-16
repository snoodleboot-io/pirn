"""``TrajectoryCallKey`` — stable, order-independent key for a step's arguments."""

from __future__ import annotations

from pirn_agents.serialization.canonical_json import CanonicalJson
from pirn_agents.serialization.opaque_policy import OpaquePolicy


class TrajectoryCallKey:
    """Build a stable JSON key from a trajectory step's arguments.

    The key is only ever compared with another key from the same process —
    :class:`~pirn_agents.evaluation.redundant_call_rate.RedundantCallRate` puts
    it in a local ``set`` and
    :class:`~pirn_agents.evaluation.tool_choice_accuracy.ToolChoiceAccuracy`
    compares two of them inline. Nothing persists it, so the encoding is free to
    change; what is *not* free is the key failing to be stable, because both
    callers read equality as "the same call was made twice" / "the agent called
    what was expected".

    **Stability is the whole contract, so it is enforced rather than hoped for**
    (PIR-826). This used to be ``json.dumps(..., default=str)``, which renders an
    argument with no content-derived ``__str__`` as ``<Foo object at 0x...>``.
    Two structurally identical calls then produced different keys, so
    ``RedundantCallRate`` under-counted redundancy and ``ToolChoiceAccuracy``
    scored a correct call as wrong — silently, and in the direction that flatters
    nothing. Routing through the shared seam with
    :attr:`~pirn_agents.serialization.opaque_policy.OpaquePolicy.STR_CONTENT`
    keeps every argument that already rendered content encoding exactly as before
    and turns the identity-keyed case into a ``TypeError``.

    Raising is the right answer *here*, unlike the hot-path digest in
    :meth:`~pirn_agents.agent.parallel_tool_executor.ParallelToolExecutor._fire_start`,
    which degrades instead: these are measurements, and a metric that quietly
    reports a wrong score is worse than one that declines to score.
    """

    def args_key(self, arguments: object) -> str:
        """Return a stable, order-independent key for a step's arguments.

        Args:
            arguments: The step's arguments, normally a mapping. Keys are sorted
                and separators are tight, so the result is independent of
                mapping order and incidental whitespace.

        Returns:
            The canonical JSON encoding of ``arguments``.

        Raises:
            TypeError: If ``arguments`` contains a leaf that renders only as its
                own memory address, which could not yield a stable key.
        """
        return CanonicalJson.encode(arguments, policy=OpaquePolicy.STR_CONTENT)
