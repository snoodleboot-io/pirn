"""``_IterativeRetrievalState`` — state threaded across retrieve-and-refine rounds."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _IterativeRetrievalState:
    """State threaded across retrieve-and-refine rounds."""

    original_query: str
    current_query: str
    merged: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    iteration: int = 0
    done: bool = False
