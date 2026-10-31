"""``SelfAskState`` — the answered sub-questions handed to the composer.

Internal API. See ``self_ask_pipeline.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SelfAskState:
    """Every sub-question paired, by position, with its answer.

    Frozen. Built once by the fan-out's ``Aggregator`` combine, then read by
    :class:`SelfAskComposer`, which zips the two tuples strictly — so they are
    always the same length and always in sub-question order.

    Attributes:
        subquestions: The sub-question list decomposition produced.
        subanswers: Each sub-question's answer, in sub-question order.
    """

    subquestions: tuple[str, ...]
    subanswers: tuple[str, ...]
