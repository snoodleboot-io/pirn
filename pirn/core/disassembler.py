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

    A ``Disassembler`` sits between the domain pipeline and a connector sink
    knot.  Its sole responsibility is to translate a well-typed domain
    ``Payload`` subclass into raw, transport-specific Python values
    (``bytes``, ``list[tuple]``, ``dict``, etc.) that the downstream
    connector knot can write.

    Subclasses must implement ``process()`` with a typed ``Payload`` input
    parameter and return raw Python types matching the connector sink's
    expected inputs.  No I/O is performed inside a disassembler; all network
    and storage access is handled by the downstream connector knot.

    Algorithm:
        1. Receive a ``Payload`` subclass instance as the named ``process()``
           argument.
        2. Extract and coerce domain fields into the raw types expected by the
           target connector (e.g. serialise to ``bytes``, flatten to
           ``list[tuple]``, or build a ``dict``).
        3. Return the raw value(s).
        No side effects, no I/O.

    References:
        docs/contributing/assembler-disassembler-pattern.md — naming
        conventions, folder layout, and pairing rules with connector knots.
    """
