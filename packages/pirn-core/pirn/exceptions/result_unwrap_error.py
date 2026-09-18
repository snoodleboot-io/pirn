from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class ResultUnwrapError(PirnError, RuntimeError):
    """Raised by ``unwrap()`` on a result that holds no value.

    :meth:`~pirn.core.ok.Ok.unwrap` returns the value; an
    :class:`~pirn.core.err.Err` and a :class:`~pirn.core.skipped.Skipped` have
    none to return, so unwrapping one is a caller mistake — check ``is_ok``
    first. The message names the failure or the skip reason found instead.

    Subclasses ``RuntimeError`` in addition to ``PirnError`` so every existing
    ``except RuntimeError`` handler around an unwrap keeps working unchanged,
    while new code can narrow to this specific failure.
    """
