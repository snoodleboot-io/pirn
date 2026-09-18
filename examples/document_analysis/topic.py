"""``Topic`` — the winning topic label with its confidence and matched signals.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Topic:
    label: str
    confidence: float
    matched_signals: list[str]
