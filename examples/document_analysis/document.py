"""``Document`` — a validated title/body/source triple ready for analysis.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Document:
    title: str
    body: str
    source: str
