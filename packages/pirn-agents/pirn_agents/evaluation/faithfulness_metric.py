"""``FaithfulnessMetric`` — fraction of answer claims supported by the context."""

from __future__ import annotations

from typing import ClassVar

from pirn_agents.agent.recorded_llm_call import RecordedLlmCall
from pirn_agents.evaluation.binary_verdict_parser import BinaryVerdictParser
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.rag_sample import RagSample
from pirn_agents.evaluation.sentence_splitter import SentenceSplitter
from pirn_agents.llm.llm_provider import LLMProvider


class FaithfulnessMetric:
    """RAGAS-style faithfulness: are the answer's claims grounded in context?

    Formula
    -------
    The answer is decomposed into claims (sentences); each claim is put to a
    pluggable judge (``supported by the context — yes/no?``). The score is::

        faithfulness = supported_claims / total_claims

    and lies in ``[0.0, 1.0]`` (1.0 = every claim is grounded; a contradictory
    or hallucinated answer trends toward 0.0). An empty answer has no claims to
    contradict and scores 1.0 vacuously.

    The judge is provider-neutral: any
    :class:`pirn_agents.llm.llm_provider.LLMProvider` (a stub in tests, a
    real model in production) works.
    """

    #: Identity this helper's provider calls are reported under when the
    #: caller does not name the knot it runs inside.  A helper is not a
    #: knot, so there is no ``self.knot_id`` to read, and core has no
    #: ambient accessor by design — but a provider call still has to be
    #: observable on the run's emitters (ADR WS4a, PIR-873).
    _default_call_id: ClassVar[str] = "faithfulness_metric"

    def __init__(self, *, judge: LLMProvider, knot_id: str | None = None) -> None:
        """Store the judge provider used to adjudicate each claim.

        Args:
            judge: The provider consulted for each claim.
            knot_id: The enclosing knot's id, reported with every judge
                call; defaults to :attr:`_default_call_id`.

        Raises:
            TypeError: If ``judge`` is not an :class:`LLMProvider`.
        """
        if not isinstance(judge, LLMProvider):
            raise TypeError(
                f"FaithfulnessMetric: judge must be an LLMProvider, got {type(judge).__name__}"
            )
        self._judge = judge
        self._knot_id = knot_id or type(self)._default_call_id
        self._splitter = SentenceSplitter()
        self._verdict_parser = BinaryVerdictParser()

    async def evaluate(self, sample: RagSample) -> MetricResult:
        """Score ``sample``'s answer for faithfulness to its contexts.

        Raises:
            TypeError: If ``sample`` is not a :class:`RagSample`.
        """
        if not isinstance(sample, RagSample):
            raise TypeError(
                f"FaithfulnessMetric.evaluate: sample must be a RagSample, "
                f"got {type(sample).__name__}"
            )
        claims = self._splitter.split(sample.answer)
        if not claims:
            return MetricResult(
                name="faithfulness", score=1.0, detail={"claims": 0, "supported": 0}
            )
        context = "\n".join(sample.contexts)
        supported = 0
        verdicts: list[bool] = []
        for claim in claims:
            reply = await RecordedLlmCall.chat(
                knot_id=self._knot_id,
                llm=self._judge,
                messages=(
                    {
                        "role": "user",
                        "content": (
                            "Is the following claim fully supported by the context? "
                            "Answer 'yes' or 'no'.\n"
                            f"Context:\n{context}\n\nClaim: {claim}"
                        ),
                    },
                ),
            )
            verdict = self._verdict_parser.parse(str(reply.get("content", "")))
            verdicts.append(verdict)
            if verdict:
                supported += 1
        return MetricResult(
            name="faithfulness",
            score=supported / len(claims),
            detail={"claims": len(claims), "supported": supported, "verdicts": verdicts},
        )
