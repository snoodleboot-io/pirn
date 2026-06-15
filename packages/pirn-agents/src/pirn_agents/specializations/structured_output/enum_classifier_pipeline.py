"""``EnumClassifierPipeline`` — pick one label from a fixed set.

A :class:`SubTapestry` that asks the LLM to choose a single label from
a caller-supplied sequence and returns the chosen label as a string.
The model output is matched case-insensitively against the labels; if
no label matches, a :class:`ValueError` is raised so the caller surfaces
the failure rather than silently returning a wrong value.

Algorithm:
    1. Receive ``prompt``, ``llm``, and ``labels`` in :meth:`process`.
    2. Validate that ``llm`` is an :class:`LLMProvider` and ``labels`` is non-empty.
    3. Build an inner :class:`Tapestry` containing a single
       :class:`_EnumClassifierAttempt` knot.
    4. Run the inner tapestry and retrieve the classifier output.
    5. Return the chosen label string.


References:
    - :class:`pirn.core.providers.llm_provider.LLMProvider`
    - :class:`pirn_agents.specializations.structured_output._enum_classifier_attempt._EnumClassifierAttempt`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.specializations.structured_output._enum_classifier_attempt import (
    _EnumClassifierAttempt,
)


class EnumClassifierPipeline(SubTapestry):
    """LLM picks one of ``labels``; the chosen label is returned as a string."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        labels: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(prompt=prompt, llm=llm, labels=labels, _config=_config, **kwargs)

    async def process(
        self,
        prompt: str,
        llm: LLMProvider,
        labels: Sequence[str],
        **_: Any,
    ) -> Any:
        """Classify the prompt into one of the allowed labels and return the matching label string.

        Args:
            prompt: The text to classify against the configured label set.
            llm: The LLM provider to use for classification.
            labels: The sequence of allowed label strings.

        Returns:
            The label string selected by the LLM from the allowed set.

        Raises:
            TypeError: If llm is not an LLMProvider or prompt is not a string.
            ValueError: If labels is empty or the classifier produces a non-string result.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"EnumClassifierPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        labels_tuple = tuple(labels)
        if not labels_tuple:
            raise ValueError("EnumClassifierPipeline: labels must be a non-empty sequence")
        for index, label in enumerate(labels_tuple):
            if not isinstance(label, str) or not label:
                raise TypeError(
                    f"EnumClassifierPipeline: labels[{index}] must be a "
                    f"non-empty string, got {label!r}"
                )
        if not isinstance(prompt, str):
            raise TypeError(
                f"EnumClassifierPipeline: prompt must be a string, got {type(prompt).__name__}"
            )
        return _EnumClassifierAttempt(
            prompt=prompt,
            llm=llm,
            labels=labels_tuple,
            _config=KnotConfig(id="classify"),
        )
