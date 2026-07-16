"""``ContextPrecisionMetric`` — rank-weighted precision of retrieved contexts."""

from __future__ import annotations

from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.evaluation.binary_verdict import parse_binary_verdict
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.rag_sample import RagSample


class ContextPrecisionMetric:
    """RAGAS-style context precision: are relevant chunks ranked near the top?

    Formula
    -------
    A pluggable judge rules each retrieved context relevant (yes/no) to the
    query. The score is the average precision, which rewards relevant chunks
    that appear earlier in the ranking::

        precision = (1 / R) * sum_k [ precision@k * relevant_k ]

    where ``precision@k`` is the fraction of the first ``k`` contexts that are
    relevant and ``R`` is the total relevant count. It lies in ``[0.0, 1.0]``
    (1.0 = every relevant chunk precedes every irrelevant one; 0.0 = no relevant
    chunk retrieved).
    """

    def __init__(self, *, judge: LLMProvider) -> None:
        """Store the judge provider used to rule each context relevant.

        Raises:
            TypeError: If ``judge`` is not an :class:`LLMProvider`.
        """
        if not isinstance(judge, LLMProvider):
            raise TypeError(
                f"ContextPrecisionMetric: judge must be an LLMProvider, got {type(judge).__name__}"
            )
        self._judge = judge

    async def evaluate(self, sample: RagSample) -> MetricResult:
        """Score ``sample``'s retrieved contexts for rank-weighted precision.

        Raises:
            TypeError: If ``sample`` is not a :class:`RagSample`.
        """
        if not isinstance(sample, RagSample):
            raise TypeError(
                f"ContextPrecisionMetric.evaluate: sample must be a RagSample, "
                f"got {type(sample).__name__}"
            )
        if not sample.contexts:
            return MetricResult(name="context_precision", score=0.0, detail={"contexts": 0})
        relevances: list[bool] = []
        for ctx in sample.contexts:
            reply = await self._judge.chat(
                [
                    {
                        "role": "user",
                        "content": (
                            "Is the following context relevant to answering the question? "
                            "Answer 'yes' or 'no'.\n"
                            f"Question: {sample.query}\n\nContext: {ctx}"
                        ),
                    }
                ]
            )
            relevances.append(parse_binary_verdict(str(reply.get("content", ""))))
        hits = 0
        precision_sum = 0.0
        for rank, relevant in enumerate(relevances, start=1):
            if relevant:
                hits += 1
                precision_sum += hits / rank
        score = precision_sum / hits if hits else 0.0
        return MetricResult(
            name="context_precision",
            score=score,
            detail={"contexts": len(relevances), "relevant": hits, "relevances": relevances},
        )
