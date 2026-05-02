"""``EnumClassifierPipeline`` — pick one label from a fixed set.

A :class:`SubTapestry` that asks the LLM to choose a single label from
a caller-supplied sequence and returns the chosen label as a string.
The model output is matched case-insensitively against the labels; if
no label matches, a :class:`ValueError` is raised so the caller surfaces
the failure rather than silently returning a wrong value.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class _EnumClassifierAttempt(Knot):
    """Single LLM call: prompt, parse the reply, return the matched label."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: LLMProvider,
        labels: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._llm = llm
        self._labels = tuple(labels)
        self._lower_index = {label.lower(): label for label in self._labels}
        super().__init__(prompt=prompt, _config=_config, **kwargs)

    async def process(self, prompt: str, **_: Any) -> str:
        if not isinstance(prompt, str):
            raise TypeError(
                "EnumClassifierPipeline: prompt must be a string, "
                f"got {type(prompt).__name__}"
            )
        system_message = (
            "You are a classifier. Choose exactly one label from the list "
            f"{list(self._labels)!r}. Reply with the label only — no "
            "punctuation, prose, or quoting."
        )
        chat_messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]
        raw = await self._llm.chat(chat_messages)
        text = self._extract_text(raw).strip()
        for label in self._labels:
            if text == label:
                return label
        match = self._lower_index.get(text.lower())
        if match is not None:
            return match
        raise ValueError(
            "EnumClassifierPipeline: model returned "
            f"{text!r} which is not in the allowed labels "
            f"{list(self._labels)!r}"
        )

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict):
                    text = first.get("text")
                    if isinstance(text, str):
                        return text
                if isinstance(first, str):
                    return first
            text = raw.get("text")
            if isinstance(text, str):
                return text
        return str(raw)


class EnumClassifierPipeline(SubTapestry):
    """LLM picks one of ``labels``; the chosen label is returned as a string."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: LLMProvider,
        labels: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "EnumClassifierPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        labels_tuple = tuple(labels)
        if not labels_tuple:
            raise ValueError(
                "EnumClassifierPipeline: labels must be a non-empty sequence"
            )
        for index, label in enumerate(labels_tuple):
            if not isinstance(label, str) or not label:
                raise TypeError(
                    f"EnumClassifierPipeline: labels[{index}] must be a "
                    f"non-empty string, got {label!r}"
                )
        self._llm = llm
        self._labels = labels_tuple
        super().__init__(prompt=prompt, _config=_config, **kwargs)

    async def process(self, prompt: str, **_: Any) -> str:
        if not isinstance(prompt, str):
            raise TypeError(
                "EnumClassifierPipeline: prompt must be a string, "
                f"got {type(prompt).__name__}"
            )
        with Tapestry() as inner:
            _EnumClassifierAttempt(
                prompt=prompt,
                llm=self._llm,
                labels=self._labels,
                _config=KnotConfig(id="classify"),
            )
        inner_result = await self._run_inner(inner)
        choice = inner_result.outputs.get("classify")
        if not isinstance(choice, str):
            raise ValueError(
                "EnumClassifierPipeline: classifier produced "
                f"{type(choice).__name__}, expected str"
            )
        return choice
