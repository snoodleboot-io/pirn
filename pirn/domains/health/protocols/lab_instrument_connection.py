"""Interface for lab-instrument connections.

Concrete implementations talk to LIS / instrument middleware (HL7,
ASTM, vendor SDKs); knots see only :class:`LabInstrumentConnection`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class LabInstrumentConnection(PirnOpaqueValue):
    """Interface every lab-instrument connection must satisfy."""

    async def fetch_results(
        self, instrument_id: str, since: datetime
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Yield result rows produced by ``instrument_id`` since ``since``."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement fetch_results()"
        )

    async def close(self) -> None:
        """Release any underlying transport resources."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement close()"
        )
