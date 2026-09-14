"""``DocumentAssembler`` — bytes-in, no-I/O half of the document loader split.

Pairs with :class:`DocumentSource` (PIR-868): the source performs the guarded
I/O and produces ``bytes``; this assembler performs the (guard-free) decode
back to text. Per ``docs/contributing/assembler-disassembler-pattern.md``,
an Assembler receives already-materialised raw values from its connector
parent knot and performs no I/O of its own — no SSRF check, no path
resolution, no guard of any kind belongs here; those all live in
:class:`DocumentSource`'s construction and fetch.

Algorithm:
    1. Receive the resolved ``body`` bytes from the upstream
       :class:`DocumentSource`.
    2. Validate ``body`` is ``bytes``.
    3. Decode as UTF-8 (permissive: ``errors="replace"``, matching the
       decoding tolerance :class:`DocumentSourceReader` already applied to
       an HTTP response's declared charset) and return the text.

References:
    - docs/contributing/assembler-disassembler-pattern.md

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class DocumentAssembler(Assembler):
    """Decode a document source's raw bytes into text. Performs no I/O."""

    def __init__(self, *, body: Knot, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(body=body, _config=_config, **kwargs)

    async def process(self, body: bytes, **_: Any) -> str:
        """Decode ``body`` as UTF-8 text.

        Args:
            body: The raw bytes produced by the upstream :class:`DocumentSource`.

        Returns:
            The decoded text.

        Raises:
            TypeError: If ``body`` is not ``bytes``.
        """
        if not isinstance(body, bytes):
            raise TypeError(f"DocumentAssembler: body must be bytes, got {type(body).__name__}")
        return body.decode("utf-8", errors="replace")
