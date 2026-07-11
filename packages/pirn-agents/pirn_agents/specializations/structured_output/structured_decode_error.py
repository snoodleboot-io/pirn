"""``StructuredDecodeError`` — a native structured-decode path failed.

Raised by an individual native strategy (native schema, forced tool-choice, or
constrained decoding) when it is selected by capability but cannot produce a
schema-valid instance — an empty tool call, unparseable content, or a
validation failure. The unified decoder (S4) catches it to fall through to the
next available strategy and, ultimately, the extract-validate-retry pipeline.
"""

from __future__ import annotations


class StructuredDecodeError(Exception):
    """A selected native structured-output strategy failed to produce a value."""
