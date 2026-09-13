"""``SelfConsistencyEnsemble`` — majority-vote aggregation over N parallel LLM samples.

Algorithm:
    1. Receive the resolved ``prompt`` string, ``LLMProvider``, and ``samples`` count.
    2. Validate input types at process time.
    3. Fan out ``samples`` independent ``llm.chat`` calls over the same user
       message with a core :class:`~pirn.nodes.map_markers.Map` (rather than a
       hand-rolled ``asyncio.gather``), so each sample gets its own engine
       ``Result``, history record, and lineage.
    4. Extract text from each raw response.
    5. Compute a case-insensitive majority vote over the stripped answer
       strings with a :class:`~pirn.nodes.reduce_.Reduce`.
    6. Return the most common answer (original casing) as an ``AgentResponse``.

References:
    - Wang et al. (2022) "Self-Consistency Improves Chain of Thought Reasoning in Language Models"
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.map_markers import Map
from pirn.nodes.reduce_ import Reduce

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.base.resolved_value_knot import ResolvedValueKnot
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.types.messaging.agent_response import AgentResponse


class _SampleOnce(Knot):
    """Draw one independent sample from the LLM for the same prompt."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        # `sample_index` distinguishes the otherwise-identical fanned-out
        # invocations in lineage; the prompt sent to the LLM does not use it.
        sample_index: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prompt=prompt, llm=llm, sample_index=sample_index, _config=_config, **kwargs
        )

    async def process(self, prompt: str, llm: LLMProvider, sample_index: int, **_: Any) -> str:
        """Sample one answer to ``prompt``.

        Args:
            prompt: The user question.
            llm: The provider to sample from.
            sample_index: This sample's position; unused beyond lineage identity.

        Returns:
            The extracted answer text.
        """
        raw = await llm.chat(messages=[{"role": "user", "content": prompt}])
        return LlmResponseText().extract(raw)


class _MajorityVote:
    """Reduce ``combine`` target: case-insensitive majority vote over samples."""

    @staticmethod
    def combine(answers: list[str]) -> str:
        """Return the majority-vote answer, original casing, first on ties.

        Args:
            answers: The sampled answer strings.

        Returns:
            The most common stripped answer, in its first-encountered original
            casing.

        Math:
            Given normalised answers :math:`a_1, \\ldots, a_n` (stripped,
            lower-cased), the winner is
            :math:`\\arg\\max_{v} \\lvert \\{ i : a_i = v \\} \\rvert`, ties
            broken by first occurrence.
        """
        normalised = [a.strip().lower() for a in answers]
        counts: Counter[str] = Counter(normalised)
        top_normal = counts.most_common(1)[0][0]
        for original, norm in zip(answers, normalised, strict=False):
            if norm == top_normal:
                return original.strip()
        return answers[0].strip()


class SelfConsistencyEnsemble(AgentPipeline):
    """Run the same prompt N times in parallel and return the majority-vote answer.

    Each sample is sent as an independent LLM call. The final answer is
    determined by a case-insensitive majority vote over the stripped response
    strings. Ties are broken by returning the first-encountered majority
    candidate.
    """

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        samples: Knot | int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(prompt=prompt, llm=llm, samples=samples, _config=_config, **kwargs)

    async def process(self, prompt: str, llm: LLMProvider, samples: int, **_: Any) -> Knot:
        """Build the sampling graph and return its majority-vote sink knot.

        Args:
            prompt: The user question to sample multiple times.
            llm: LLM provider used to perform the chat completions.
            samples: Number of parallel LLM samples to take.

        Returns:
            The sink knot whose output is an :class:`AgentResponse` carrying
            the majority-vote answer.

        Raises:
            TypeError: If prompt is not a string or llm is not an LLMProvider.
            ValueError: If samples is not a positive int.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                f"SelfConsistencyEnsemble: prompt must be a string, got {type(prompt).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"SelfConsistencyEnsemble: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(samples, int) or samples <= 0:
            raise ValueError(
                f"SelfConsistencyEnsemble: samples must be a positive int, got {samples!r}"
            )
        indices = ResolvedValueKnot(value=list(range(samples)), _config=KnotConfig(id="indices"))
        sampled = _SampleOnce(
            prompt=prompt,
            llm=llm,
            # Core's Map marker is consumed at construction by
            # `knot.py:199-205` and is deliberately not a Knot, so it does not
            # satisfy the declared `Knot | int`. Inline suppression is the
            # house idiom for this; see PIR-715/PIR-716.
            sample_index=Map(indices),  # pyright: ignore[reportArgumentType]
            _config=KnotConfig(id="sample_each"),
        )
        winner = Reduce(
            of=sampled,
            combine=_MajorityVote.combine,
            _config=KnotConfig(id="vote"),
        )
        return _SelfConsistencyResult(winner=winner, _config=KnotConfig(id="result"))


class _SelfConsistencyResult(Knot):
    """Wrap the majority-vote answer string as an :class:`AgentResponse`."""

    def __init__(self, *, winner: Knot | str, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(winner=winner, _config=_config, **kwargs)

    async def process(self, winner: str, **_: Any) -> AgentResponse:
        """Return ``winner`` wrapped as an :class:`AgentResponse`."""
        return AgentResponse(content=winner)
