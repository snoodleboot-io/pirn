"""``EvaluationJudge`` — pairwise + rubric LLM-as-judge with bias controls."""

from __future__ import annotations

from collections.abc import Sequence

from pirn_agents.evaluation.judge_score_parser import JudgeScoreParser
from pirn_agents.evaluation.pairwise_choice_parser import PairwiseChoiceParser
from pirn_agents.evaluation.pairwise_outcome import PairwiseOutcome
from pirn_agents.evaluation.rubric_criterion import RubricCriterion
from pirn_agents.evaluation.rubric_score import RubricScore
from pirn_agents.llm_provider import LLMProvider


class EvaluationJudge:
    """An LLM-as-judge harness supporting rubric and pairwise scoring modes.

    Constructed (``init``) with a provider-neutral judge
    :class:`~pirn_agents.llm_provider.LLMProvider` (a stub in tests, any
    model in production) and two bias controls, then invoked (``process``) per
    evaluation:

    * **self-consistency** — each judgement is sampled ``self_consistency``
      times and aggregated (mean score for rubric, majority vote for pairwise),
      damping single-sample noise.
    * **position-swap** — pairwise judging is run in both A/B orders; a winner
      that does not hold across both orders is downgraded to a tie with
      ``consistent=False``, exposing position bias rather than trusting it.

    No vendor is privileged: the judge is an injected interface, and every
    prompt is provider-agnostic plain text.
    """

    def __init__(
        self,
        *,
        judge: LLMProvider,
        self_consistency: int = 1,
        position_swap: bool = False,
    ) -> None:
        """Configure the judge provider and bias controls.

        Args:
            judge: The provider that returns a textual verdict for each prompt.
            self_consistency: Number of samples drawn per judgement (>= 1).
            position_swap: Run pairwise judging in both orders and require
                agreement.

        Raises:
            TypeError: If ``judge`` is not an :class:`LLMProvider` or
                ``position_swap`` is not a bool.
            ValueError: If ``self_consistency`` is not a positive int.
        """
        if not isinstance(judge, LLMProvider):
            raise TypeError(
                f"EvaluationJudge: judge must be an LLMProvider, got {type(judge).__name__}"
            )
        if isinstance(self_consistency, bool) or not isinstance(self_consistency, int):
            raise TypeError(
                f"EvaluationJudge: self_consistency must be an int, got {type(self_consistency).__name__}"
            )
        if self_consistency < 1:
            raise ValueError(
                f"EvaluationJudge: self_consistency must be >= 1, got {self_consistency}"
            )
        if not isinstance(position_swap, bool):
            raise TypeError(
                f"EvaluationJudge: position_swap must be a bool, got {type(position_swap).__name__}"
            )
        self._judge = judge
        self._self_consistency = self_consistency
        self._position_swap = position_swap
        self._score_parser = JudgeScoreParser()
        self._choice_parser = PairwiseChoiceParser()

    async def score_rubric(
        self,
        *,
        prompt: str,
        response: str,
        criteria: Sequence[RubricCriterion],
    ) -> RubricScore:
        """Score ``response`` to ``prompt`` against each weighted rubric criterion.

        Each criterion is scored on ``[0, 1]`` (self-consistency samples are
        averaged); the overall is the weight-average across criteria.

        Raises:
            TypeError: If any element of ``criteria`` is not a
                :class:`RubricCriterion`.
            ValueError: If ``criteria`` is empty.
        """
        criteria_list = list(criteria)
        if not criteria_list:
            raise ValueError("EvaluationJudge.score_rubric: at least one criterion is required")
        for index, criterion in enumerate(criteria_list):
            if not isinstance(criterion, RubricCriterion):
                raise TypeError(
                    f"EvaluationJudge.score_rubric: criteria[{index}] must be a RubricCriterion, "
                    f"got {type(criterion).__name__}"
                )
        per_criterion: dict[str, float] = {}
        samples_detail: dict[str, list[float]] = {}
        for criterion in criteria_list:
            samples: list[float] = []
            for _ in range(self._self_consistency):
                reply = await self._judge.chat(
                    [
                        {
                            "role": "user",
                            "content": (
                                "Score the response for the criterion on a 0.0-1.0 scale. "
                                "Reply with just the number.\n"
                                f"Criterion: {criterion.name} — {criterion.description}\n"
                                f"Prompt: {prompt}\n\nResponse: {response}"
                            ),
                        }
                    ]
                )
                samples.append(self._score_parser.parse(str(reply.get("content", ""))))
            per_criterion[criterion.name] = sum(samples) / len(samples)
            samples_detail[criterion.name] = samples
        total_weight = sum(c.weight for c in criteria_list)
        overall = sum(per_criterion[c.name] * c.weight for c in criteria_list) / total_weight
        return RubricScore(
            overall=overall,
            per_criterion=per_criterion,
            detail={"samples": samples_detail, "self_consistency": self._self_consistency},
        )

    async def compare_pairwise(
        self,
        *,
        prompt: str,
        response_a: str,
        response_b: str,
    ) -> PairwiseOutcome:
        """Judge whether ``response_a`` or ``response_b`` better answers ``prompt``.

        Runs ``self_consistency`` votes per presentation order; with
        ``position_swap`` enabled it also runs the swapped order and forces a tie
        (``consistent=False``) when the two orders disagree.
        """
        orders: list[tuple[str, str]] = [("a", "b")]
        if self._position_swap:
            orders.append(("b", "a"))
        votes_a = 0
        votes_b = 0
        ties = 0
        order_winners: list[str] = []
        for first, second in orders:
            first_text = response_a if first == "a" else response_b
            second_text = response_a if second == "a" else response_b
            order_a = 0
            order_b = 0
            for _ in range(self._self_consistency):
                reply = await self._judge.chat(
                    [
                        {
                            "role": "user",
                            "content": (
                                "Which response better answers the prompt? "
                                "Reply with 'A', 'B', or 'tie'.\n"
                                f"Prompt: {prompt}\n\n"
                                f"Response A: {first_text}\n\nResponse B: {second_text}"
                            ),
                        }
                    ]
                )
                presented = self._choice_parser.parse(str(reply.get("content", "")))
                if presented == "tie":
                    ties += 1
                    continue
                winner_real = first if presented == "a" else second
                if winner_real == "a":
                    votes_a += 1
                    order_a += 1
                else:
                    votes_b += 1
                    order_b += 1
            order_winners.append("a" if order_a > order_b else "b" if order_b > order_a else "tie")
        total = votes_a + votes_b + ties
        score_a = votes_a / total if total else 0.0
        score_b = votes_b / total if total else 0.0
        consistent = len(set(order_winners)) == 1 if self._position_swap else True
        if self._position_swap and not consistent:
            winner = "tie"
        else:
            winner = "a" if votes_a > votes_b else "b" if votes_b > votes_a else "tie"
        return PairwiseOutcome(
            winner=winner,
            score_a=score_a,
            score_b=score_b,
            consistent=consistent,
            detail={
                "votes_a": votes_a,
                "votes_b": votes_b,
                "ties": ties,
                "order_winners": order_winners,
                "position_swap": self._position_swap,
                "self_consistency": self._self_consistency,
            },
        )
