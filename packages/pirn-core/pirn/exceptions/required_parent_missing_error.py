from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class RequiredParentMissingError(PirnError, RuntimeError):
    """The synthetic failure a ``REQUIRE_ALL_PARENTS`` knot records instead of running.

    Under ``ErrorPolicy.REQUIRE_ALL_PARENTS`` a knot runs only when every parent
    produced a value. When one did not, the engine never calls the knot and
    records this in the knot's :class:`~pirn.core.err.Err` instead, so a reader
    of the lineage row can tell "a parent did not deliver" from an exception the
    knot itself raised — which a bare ``RuntimeError`` cannot.

    Subclasses ``RuntimeError`` in addition to ``PirnError`` so any handler
    written against the previous synthetic ``RuntimeError`` keeps working.
    """
