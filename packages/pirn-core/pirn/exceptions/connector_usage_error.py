from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class ConnectorUsageError(PirnError, RuntimeError):
    """Raised when a connector is driven in a way its protocol forbids.

    Not a configuration problem and not a backend failure: the call itself is
    wrong for the object it was made on — ``close()`` on a transaction handle
    whose ``async with`` scope owns the connection, a nested ``transaction()``
    on a handle already inside one, a statement issued on a pool from inside
    its own transaction scope (which would deadlock on the scope's lock).

    Subclasses ``RuntimeError`` in addition to ``PirnError`` so every existing
    ``except RuntimeError`` handler around a connector call keeps working
    unchanged, while new code can narrow to this specific failure.
    """
