"""Signal-domain typed values.

Each value is a frozen :mod:`dataclasses` dataclass that mixes in
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue` so pydantic IO
validation between knots short-circuits to an ``isinstance`` check.
"""
