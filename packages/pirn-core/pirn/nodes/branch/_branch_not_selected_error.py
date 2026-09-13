from __future__ import annotations


class _BranchNotSelectedError(Exception):
    """Internal signal: this branch arm was not chosen by the selector."""
