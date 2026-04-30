from __future__ import annotations


class _BranchNotSelected(Exception):
    """Internal signal: this branch arm was not chosen by the selector."""
