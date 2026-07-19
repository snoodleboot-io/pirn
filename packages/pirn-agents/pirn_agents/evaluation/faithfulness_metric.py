"""``FaithfulnessMetric`` — fraction of answer claims supported by the context."""

from __future__ import annotations

from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.evaluation.binary_verdict_parser import BinaryVerdictParser
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.rag_sample import RagSample
from pirn_agents.evaluation.sentence_splitter import SentenceSplitter


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
    :class:`pirn.core.providers.llm_provider.LLMProvider` (a stub in tests, a
    real model in production) works.
    """

    def __init__(self, *, judge: LLMProvider) -> None:
        """Store the judge provider used to adjudicate each claim.

        Raises:
            TypeError: If ``judge`` is not an :class:`LLMProvider`.
        """
        if not isinstance(judge, LLMProvider):
            raise TypeError(
                f"FaithfulnessMetric: judge must be an LLMProvider, got {type(judge).__name__}"
            )
        self._judge = judge
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
            reply = await self._judge.chat(
                [
                    {
                        "role": "user",
                        "content": (
                            "Is the following claim fully supported by the context? "
                            "Answer 'yes' or 'no'.\n"
                            f"Context:\n{context}\n\nClaim: {claim}"
                        ),
                    }
                ]
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
