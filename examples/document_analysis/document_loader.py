"""``DocumentLoader`` — validates and packages raw article fields into a ``Document``.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.document_analysis.document import Document


class DocumentLoader(Knot):
    """Validates and packages raw article fields into a ``Document``.

    Trims whitespace and enforces non-empty title + body.
    """

    async def process(self, title: str, body: str, source: str, **_: Any) -> Document:
        title = title.strip()
        body = body.strip()
        if not title:
            raise ValueError("Document title must not be empty")
        if not body:
            raise ValueError("Document body must not be empty")
        return Document(title=title, body=body, source=source)
