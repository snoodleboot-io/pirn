"""``ScoreAggregator`` — combine judge samples into scores and winners."""

from __future__ import annotations

from collections.abc import Sequence


class ScoreAggregator:
    """Aggregate raw judge samples into rubric scores and pairwise outcomes.

    Concentrates the numeric reduction logic — self-consistency means, weighted
    overalls, vote fractions, majority votes, and position-swap reconciliation —
    so the judge holds only the orchestration (which prompts to send in which
    order) and none of the arithmetic.
    """

    def mean(self, values: Sequence[float]) -> float:
        """Return the arithmetic mean of ``values`` (self-consistency average).

        Args:
            values: One or more sampled scores for a single criterion.

        Returns:
            The mean of ``values``.
        """
        return sum(values) / len(values)

    def weighted_mean(self, values: Sequence[float], weights: Sequence[float]) -> float:
        """Return the weight-averaged combination of ``values``.

        Args:
            values: Per-criterion scores, aligned with ``weights``.
            weights: Positive relative weights, aligned with ``values``.

        Returns:
            ``sum(value * weight) / sum(weight)``.
        """
        total_weight = sum(weights)
        return (
            sum(value * weight for value, weight in zip(values, weights, strict=True))
            / total_weight
        )

    def fraction(self, count: int, total: int) -> float:
        """Return ``count / total`` as a fraction, or ``0.0`` when ``total`` is 0.

        Args:
            count: The numerator (a subset vote tally).
            total: The denominator (all votes cast).

        Returns:
            The fraction in ``[0.0, 1.0]``, or ``0.0`` when no votes were cast.
        """
        return count / total if total else 0.0

    def majority(self, count_a: int, count_b: int) -> str:
        """Return the majority winner between two tallies.

        Args:
            count_a: Votes for ``"a"``.
            count_b: Votes for ``"b"``.

        Returns:
            ``"a"`` or ``"b"`` for a strict majority, else ``"tie"``.
        """
        if count_a > count_b:
            return "a"
        if count_b > count_a:
            return "b"
        return "tie"

    def orders_consistent(self, order_winners: Sequence[str]) -> bool:
        """Return whether every presentation order agreed on a winner.

        Args:
            order_winners: One winner label per presentation order.

        Returns:
            ``True`` when all entries are identical.
        """
        return len(set(order_winners)) == 1

    def resolve_winner(
        self,
        *,
        votes_a: int,
        votes_b: int,
        position_swap: bool,
        consistent: bool,
    ) -> str:
        """Reconcile the overall pairwise winner, honouring position-swap bias.

        When position-swap is enabled and the orders disagreed, the winner is
        downgraded to ``"tie"``; otherwise the overall majority wins.

        Args:
            votes_a: Total votes for real response ``"a"``.
            votes_b: Total votes for real response ``"b"``.
            position_swap: Whether both presentation orders were run.
            consistent: Whether those orders agreed (see :meth:`orders_consistent`).

        Returns:
            ``"a"``, ``"b"``, or ``"tie"``.
        """
        if position_swap and not consistent:
            return "tie"
        return self.majority(votes_a, votes_b)
