"""``StructuredOutputCapability`` — a provider's native structured-output support.

A small, provider-neutral value object describing which native, single-pass
structured-output mechanisms a provider advertises. It is the capability
surface F20 gates on: the unified decoder (S4) consults these flags to choose
native schema decoding (S1), forced tool-choice extraction (S2), or
grammar/regex-constrained decoding (S3), and falls back to the existing
extract-validate-retry pipeline when none are advertised.

The object names no vendor and carries no wire shapes — each provider decides
its own flags and owns the request shaping behind its adapter boundary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StructuredOutputCapability:
    """Flags describing a provider's native structured-output mechanisms.

    Attributes
    ----------
    native_schema:
        Whether the provider accepts a native schema/``response_format`` request
        that guarantees schema-valid JSON content in one pass.
    forced_tool_choice:
        Whether the provider can be forced to emit a single named tool call,
        so a synthetic extraction tool guarantees structured arguments.
    constrained_decoding:
        Whether the provider (typically a local engine) supports
        grammar/regex-constrained decoding passed through its decode options.
    """

    native_schema: bool = False
    forced_tool_choice: bool = False
    constrained_decoding: bool = False
