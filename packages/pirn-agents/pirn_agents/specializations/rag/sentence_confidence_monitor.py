"""``SentenceConfidenceMonitor`` — flag a low-confidence sentence for retrieval.

FLARE regenerates with retrieval whenever the model is about to assert something
it is unsure about. This knot is the confidence gate: given a generated sentence
and its confidence score, it reports whether that sentence should trigger a
retrieval call (confidence below ``threshold``). The same rule is exposed as
:meth:`needs_retrieval` so a hand-rolled FLARE loop can share it.

Algorithm:
    1. Validate ``sentence`` (str), ``confidence`` (number in [0, 1]), and
       ``threshold`` (number in [0, 1]).
    2. Return ``True`` when ``confidence < threshold``, else ``False``.

References:
    - Jiang et al., "Active Retrieval Augmented Generation" (FLARE, EMNLP 2023):
      https://arxiv.org/abs/2305.06983
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SentenceConfidenceMonitor(Knot):
    """Report whether a sentence's confidence is below the retrieval threshold."""

    def __init__(
        self,
        *,
        sentence: Knot | str,
        confidence: Knot | float,
        _config: KnotConfig,
        threshold: Knot | float = 0.5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            sentence=sentence,
            confidence=confidence,
            threshold=threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        sentence: str,
        confidence: float,
        threshold: float = 0.5,
        **_: Any,
    ) -> bool:
        """Return whether ``sentence`` should trigger a retrieval call.

        Args:
            sentence: The generated sentence being monitored.
            confidence: The model's confidence in the sentence, in [0, 1].
            threshold: The confidence below which retrieval is triggered.

        Returns:
            ``True`` when ``confidence < threshold``.

        Raises:
            TypeError: If ``sentence`` is not a string or the scores are not numbers.
            ValueError: If ``confidence`` or ``threshold`` is outside [0, 1].
        """
        if not isinstance(sentence, str):
            raise TypeError(
                f"SentenceConfidenceMonitor: sentence must be a string, "
                f"got {type(sentence).__name__}"
            )
        if not isinstance(confidence, (int, float)):
            raise TypeError(
                f"SentenceConfidenceMonitor: confidence must be a number, "
                f"got {type(confidence).__name__}"
            )
        if not isinstance(threshold, (int, float)):
            raise TypeError(
                f"SentenceConfidenceMonitor: threshold must be a number, "
                f"got {type(threshold).__name__}"
            )
        if not 0.0 <= float(confidence) <= 1.0:
            raise ValueError(
                f"SentenceConfidenceMonitor: confidence must be in [0, 1], got {confidence!r}"
            )
        if not 0.0 <= float(threshold) <= 1.0:
            raise ValueError(
                f"SentenceConfidenceMonitor: threshold must be in [0, 1], got {threshold!r}"
            )
        return self.needs_retrieval(float(confidence), float(threshold))

    @staticmethod
    def needs_retrieval(confidence: float, threshold: float) -> bool:
        """Return whether ``confidence`` falls below ``threshold``."""
        return confidence < threshold
