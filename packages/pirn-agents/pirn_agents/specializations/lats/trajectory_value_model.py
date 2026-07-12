"""``TrajectoryValueModel`` — pluggable value estimator for LATS search.

The value model scores a partial action trajectory; LATS uses it to decide which
frontier node to expand next. It is an interface so it can be stubbed in CI (a
deterministic double) or backed by an LLM/learned critic in production. Treated as
opaque by pydantic (see :class:`PirnOpaqueValue`).
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class TrajectoryValueModel(PirnOpaqueValue):
    """Interface every trajectory value estimator must satisfy."""

    async def score(self, task: str, trajectory: Sequence[str]) -> float:
        """Return a scalar value estimate for ``trajectory`` under ``task``.

        Higher is better. Implementations must be deterministic for a given
        input when used under test.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement score()")
