"""``FunnelAnalysisKnot`` — step-by-step funnel conversion analysis.

Given an ordered list of event names (the funnel steps) and a column
that identifies the user, the knot computes how many users reached each
step.  Users must complete steps in order to be counted at a later step.

The result is one row per step with:
  * ``step``         — step name
  * ``step_index``   — 0-based position in the funnel
  * ``users``        — distinct users who reached this step
  * ``conversion``   — fraction of users at the previous step who reached
                       this step (None for step 0)
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class FunnelAnalysisKnot(Knot):
    """Compute per-step conversion rates for an ordered event funnel."""

    def __init__(
        self,
        *,
        rows: Knot,
        user_column: str,
        event_column: str,
        funnel_steps: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        IdentifierValidator.validate_column("user_column", user_column)
        IdentifierValidator.validate_column("event_column", event_column)
        if not funnel_steps or not isinstance(funnel_steps, (list, tuple)):
            raise ValueError(
                "FunnelAnalysisKnot: funnel_steps must be a non-empty sequence"
            )
        self._user_column = user_column
        self._event_column = event_column
        self._funnel_steps = list(funnel_steps)
        super().__init__(rows=rows, _config=_config, **kwargs)

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Compute funnel conversion rates from event rows.

        A user is counted at step N only if they have also appeared at all
        prior steps (strict ordered completion).

        Args:
            rows: Upstream event rows with ``user_column`` and ``event_column``.

        Returns:
            One dict per funnel step with ``step``, ``step_index``, ``users``,
            and ``conversion``.
        """
        user_events: dict[Any, set[str]] = {}
        for row in rows:
            user = row.get(self._user_column)
            event = row.get(self._event_column)
            user_events.setdefault(user, set()).add(event)

        step_users: list[set[Any]] = []
        qualified: set[Any] | None = None
        for step in self._funnel_steps:
            if qualified is None:
                reached = {u for u, evts in user_events.items() if step in evts}
            else:
                reached = {u for u in qualified if step in user_events.get(u, set())}
            step_users.append(reached)
            qualified = reached

        result: list[dict[str, Any]] = []
        for idx, (step, users) in enumerate(zip(self._funnel_steps, step_users)):
            prev_count = len(step_users[idx - 1]) if idx > 0 else None
            conversion = (
                len(users) / prev_count if prev_count else None
            )
            result.append(
                {
                    "step": step,
                    "step_index": idx,
                    "users": len(users),
                    "conversion": conversion,
                }
            )
        return result
