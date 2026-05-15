"""``Assembler`` — marker base class for all pirn assembler knots.

An Assembler converts raw connector output (``bytes``, ``list[tuple]``, etc.)
into a domain ``Payload`` subclass. It performs no I/O — raw values arrive
already materialised from a connector parent knot.

See ``docs/contributing/assembler-disassembler-pattern.md`` for the full
contract, naming convention, and folder layout.
"""

from __future__ import annotations

from pirn.core.knot import Knot


class Assembler(Knot):
    """Marker base for assembler knots.

    Subclasses must implement ``process()`` accepting raw Python types and
    returning a ``Payload`` subclass. No additional behaviour is added here —
    this base exists for classification and type-checking purposes.
    """
