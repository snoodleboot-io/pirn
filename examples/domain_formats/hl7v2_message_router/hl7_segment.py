"""``Hl7Segment`` — positional field access shared by the three parsing knots.

HL7v2 segments are ragged: a trailing field that carries no value is simply
absent, so every parser needs "the field at this index, or a default". This
is the one place that logic lives.

Part of the ``examples.domain_formats.hl7v2_message_router`` example.
"""

from __future__ import annotations

from typing import Any


class Hl7Segment:
    """Reads fields out of the ``{"segment_id": ..., "fields": [...]}`` records."""

    @staticmethod
    def fields_of(segments: list[dict[str, Any]], segment_id: str) -> list[str]:
        """The fields of the first segment with ``segment_id``, or an empty list."""
        for segment in segments:
            if segment["segment_id"] == segment_id:
                return segment["fields"]
        return []

    @staticmethod
    def field(fields: list[str], index: int, default: str = "") -> str:
        """The field at ``index``, or ``default`` when the segment stops short of it."""
        return fields[index] if index < len(fields) else default
