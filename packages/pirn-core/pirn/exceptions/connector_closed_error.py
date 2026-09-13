from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class ConnectorClosedError(PirnError, RuntimeError):
    """Raised when a connector or pool is used after it has been closed.

    Subclasses ``RuntimeError`` in addition to ``PirnError`` so every
    existing ``except RuntimeError`` handler around a connector call keeps
    working unchanged, while new code can narrow to this specific failure.
    """
