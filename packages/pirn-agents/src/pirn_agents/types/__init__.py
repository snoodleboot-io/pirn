"""Frozen dataclass value types used across the agent knots.

These are pure-Python values that flow through the agent pipeline:
messages, contexts, plans, tool calls, tool results, and final
responses. None of them carry engine state — they wrap primitives and
hash-equal naturally for content addressing.
"""

__all__: list[str] = []
