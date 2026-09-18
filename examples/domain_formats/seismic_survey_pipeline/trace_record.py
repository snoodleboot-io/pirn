"""``TraceRecord`` — one SEG-Y trace as emitted by ``SegyFormat.decode()``.

Part of the ``examples.domain_formats.seismic_survey_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TraceRecord:
    """Matches the record schema emitted by ``SegyFormat.decode()``."""

    trace_index: int
    header: dict[str, Any]
    data: bytes
