"""``TriageIds`` — the well-known knot ids this example's outputs are read by.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

from typing import ClassVar


class TriageIds:
    """Knot ids shared by the decider that registers them and the driver."""

    complete: ClassVar[str] = "triage_complete"
