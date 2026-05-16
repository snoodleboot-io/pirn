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

    An ``Assembler`` sits between a connector source knot and the rest of the
    domain pipeline.  Its sole responsibility is to translate raw, transport-
    specific Python values (``bytes``, ``list[tuple]``, ``dict``, etc.) into a
    well-typed domain ``Payload`` subclass.

    Subclasses must implement ``process()`` with typed input parameters
    matching the connector's output fields and a return type that is a
    ``Payload`` subclass.  No I/O is performed inside an assembler; all
    network and storage access is handled by the upstream connector knot.

    Algorithm:
        1. Receive raw connector output as named ``process()`` arguments.
        2. Validate and coerce fields into the target ``Payload`` model using
           standard Pydantic construction or explicit field mapping.
        3. Return the populated ``Payload`` instance.
        No side effects, no I/O.

    References:
        docs/contributing/assembler-disassembler-pattern.md — naming
        conventions, folder layout, and pairing rules with connector knots.
    """
