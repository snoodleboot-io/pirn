"""``ContextRecallMetric`` — fraction of the gold answer covered by contexts."""

from __future__ import annotations

from pirn_agents.evaluation.binary_verdict_parser import BinaryVerdictParser
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.rag_sample import RagSample
from pirn_agents.evaluation.sentence_splitter import SentenceSplitter
from pirn_agents.llm_provider import LLMProvider


class ContextRecallMetric:
    """RAGAS-style context recall: is the gold answer attributable to context?

    Formula
    -------
    The ``ground_truth`` reference answer is decomposed into sentences; each is
    put to a pluggable judge (``can this be attributed to the retrieved
    context — yes/no?``). The score is::

        recall = attributable_sentences / total_sentences

    and lies in ``[0.0, 1.0]`` (1.0 = the retrieved context covers everything
    the gold answer states; low = the retriever missed supporting evidence).

    Requires ``sample.ground_truth`` to be set.
    """

    def __init__(self, *, judge: LLMProvider) -> None:
        """Store the judge provider used to adjudicate attribution.

        Raises:
            TypeError: If ``judge`` is not an :class:`LLMProvider`.
        """
        if not isinstance(judge, LLMProvider):
            raise TypeError(
                f"ContextRecallMetric: judge must be an LLMProvider, got {type(judge).__name__}"
            )
        self._judge = judge
        self._splitter = SentenceSplitter()
        self._verdict_parser = BinaryVerdictParser()

    async def evaluate(self, sample: RagSample) -> MetricResult:
        """Score how much of ``sample.ground_truth`` the contexts support.

        Raises:
            TypeError: If ``sample`` is not a :class:`RagSample`.
            ValueError: If ``sample.ground_truth`` is ``None``.
        """
        if not isinstance(sample, RagSample):
            raise TypeError(
                f"ContextRecallMetric.evaluate: sample must be a RagSample, "
                f"got {type(sample).__name__}"
            )
        if sample.ground_truth is None:
            raise ValueError("ContextRecallMetric.evaluate: sample.ground_truth is required")
        sentences = self._splitter.split(sample.ground_truth)
        if not sentences:
            return MetricResult(name="context_recall", score=1.0, detail={"sentences": 0})
        context = "\n".join(sample.contexts)
        attributed = 0
        verdicts: list[bool] = []
        for sentence in sentences:
            reply = await self._judge.chat(
                [
                    {
                        "role": "user",
                        "content": (
                            "Can the following statement be attributed to the context? "
                            "Answer 'yes' or 'no'.\n"
                            f"Context:\n{context}\n\nStatement: {sentence}"
                        ),
                    }
                ]
            )
            verdict = self._verdict_parser.parse(str(reply.get("content", "")))
            verdicts.append(verdict)
            if verdict:
                attributed += 1
        return MetricResult(
            name="context_recall",
            score=attributed / len(sentences),
            detail={"sentences": len(sentences), "attributed": attributed, "verdicts": verdicts},
        )
