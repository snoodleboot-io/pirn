"""Agent guardrail pipelines.

Each pipeline is a :class:`SubTapestry` that runs safety checks on the
boundary between the user / LLM / tool surface: input scrubbing,
output validation, fact-checking, and PII redaction.
"""

__all__: list[str] = []
