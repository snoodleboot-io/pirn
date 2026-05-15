"""``Disassembler`` — marker base class for all pirn disassembler knots.

A Disassembler converts a domain ``Payload`` subclass into raw types
(``bytes``, ``list[tuple]``, etc.) suitable for a connector sink knot. It
performs no I/O — the raw values it produces are passed to a downstream
connector knot which handles the actual write.

See ``docs/contributing/assembler-disassembler-pattern.md`` for the full
contract, naming convention, and folder layout.
"""

from __future__ import annotations

from pirn.core.knot import Knot


class Disassembler(Knot):
    """Marker base for disassembler knots.

    Subclasses must implement ``process()`` accepting a ``Payload`` subclass
    and returning raw Python types. No additional behaviour is added here —
    this base exists for classification and type-checking purposes.
    """
