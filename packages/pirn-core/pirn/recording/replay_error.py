"""Base error for every way a replay can refuse to proceed."""

from __future__ import annotations


class ReplayError(Exception):
    """A replay could not serve a recorded outcome and refused to execute.

    Replay never falls back to live execution.  A run started in replay
    posture either serves every knot from the recording or raises: silently
    re-executing would turn a determinism guarantee into a coin flip, and the
    caller would have no way to tell which they got.

    Subclasses distinguish *why* the recording could not be honoured —
    ``ReplayMismatchError`` when the recording does not describe this
    computation, ``ReplayValueUnavailableError`` when it does but the value
    itself is gone from the ``DataStore``.
    """
