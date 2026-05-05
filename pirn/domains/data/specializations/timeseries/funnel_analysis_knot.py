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

Algorithm:
    1. Receive resolved ``rows``, ``user_column``, ``event_column``, and
       ``funnel_steps`` in ``process()``.
    2. Validate column identifiers and non-empty funnel_steps.
    3. Build a ``user_events`` map: user → set of distinct event names.
    4. For each step (in order), intersect the qualified set from the prior
       step with users who have that event.
    5. Compute ``conversion = |step_N| / |step_{N-1}|`` (None for step 0).
    6. Return one dict per step sorted by ``step_index``.

Math:
    $conversion_i = \\frac{|users_i|}{|users_{i-1}|}$ for $i > 0$

References:
    [1] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class FunnelAnalysisKnot(Knot):
    """Compute per-step conversion rates for an ordered event funnel."""

    def __init__(
        self,
        *,
        rows: Knot | list,
        user_column: Knot | str,
        event_column: Knot | str,
        funnel_steps: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            user_column=user_column,
            event_column=event_column,
            funnel_steps=funnel_steps,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        rows: Any,
        user_column: Any,
        event_column: Any,
        funnel_steps: Any,
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Compute funnel conversion rates from event rows.

        A user is counted at step N only if they have also appeared at all
        prior steps (strict ordered completion).

        Args:
            rows: Upstream event rows with ``user_column`` and ``event_column``.
            user_column: Column name identifying the user.
            event_column: Column name for the event type.
            funnel_steps: Ordered sequence of event names defining the funnel.

        Returns:
            One dict per funnel step with ``step``, ``step_index``, ``users``,
            and ``conversion``.
        """
        IdentifierValidator.validate_column("user_column", user_column)
        IdentifierValidator.validate_column("event_column", event_column)
        if not funnel_steps or not isinstance(funnel_steps, (list, tuple)):
            raise ValueError(
                "FunnelAnalysisKnot: funnel_steps must be a non-empty sequence"
            )

        steps = list(funnel_steps)
        user_events: dict[Any, set[str]] = {}
        for row in rows:
            user = row.get(user_column)
            event = row.get(event_column)
            user_events.setdefault(user, set()).add(event)

        step_users: list[set[Any]] = []
        qualified: set[Any] | None = None
        for step in steps:
            if qualified is None:
                reached = {u for u, evts in user_events.items() if step in evts}
            else:
                reached = {u for u in qualified if step in user_events.get(u, set())}
            step_users.append(reached)
            qualified = reached

        result: list[dict[str, Any]] = []
        for idx, (step, users) in enumerate(zip(steps, step_users, strict=False)):
            prev_count = len(step_users[idx - 1]) if idx > 0 else None
            conversion = len(users) / prev_count if prev_count else None
            result.append(
                {
                    "step": step,
                    "step_index": idx,
                    "users": len(users),
                    "conversion": conversion,
                }
            )
        return result
