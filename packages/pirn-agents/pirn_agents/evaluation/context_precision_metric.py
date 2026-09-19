"""``ContextPrecisionMetric`` — rank-weighted precision of retrieved contexts."""

from __future__ import annotations

from typing import ClassVar

from pirn_agents.agent.recorded_llm_call import RecordedLlmCall
from pirn_agents.evaluation.binary_verdict_parser import BinaryVerdictParser
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.rag_sample import RagSample
from pirn_agents.llm.llm_provider import LLMProvider


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

    #: Identity this helper's provider calls are reported under when the
    #: caller does not name the knot it runs inside.  A helper is not a
    #: knot, so there is no ``self.knot_id`` to read, and core has no
    #: ambient accessor by design — but a provider call still has to be
    #: observable on the run's emitters (ADR WS4a, PIR-873).
    _default_call_id: ClassVar[str] = "context_precision_metric"

    def __init__(self, *, judge: LLMProvider, knot_id: str | None = None) -> None:
        """Store the judge provider used to rule each context relevant.

        Args:
            judge: The provider consulted for each retrieved context.
            knot_id: The enclosing knot's id, reported with every judge
                call; defaults to :attr:`_default_call_id`.

        Raises:
            TypeError: If ``judge`` is not an :class:`LLMProvider`.
        """
        if not isinstance(judge, LLMProvider):
            raise TypeError(
                f"ContextPrecisionMetric: judge must be an LLMProvider, got {type(judge).__name__}"
            )
        self._judge = judge
        self._knot_id = knot_id or type(self)._default_call_id
        self._verdict_parser = BinaryVerdictParser()

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
            reply = await RecordedLlmCall.chat(
                knot_id=self._knot_id,
                llm=self._judge,
                messages=(
                    {
                        "role": "user",
                        "content": (
                            "Is the following context relevant to answering the question? "
                            "Answer 'yes' or 'no'.\n"
                            f"Question: {sample.query}\n\nContext: {ctx}"
                        ),
                    },
                ),
            )
            relevances.append(self._verdict_parser.parse(str(reply.get("content", ""))))
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
