"""Interface for SCADA / historian connections used by the production knots."""

from __future__ import annotations

from datetime import datetime
from typing import AsyncIterator, Mapping

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class HistorianConnection(PirnOpaqueValue):
    """Interface every historian / SCADA connection implementation must satisfy.

    Concrete adapters (OSIsoft PI, AVEVA Historian, vendor REST gateways)
    inherit and override every method. Pirn treats the connection as
    opaque (see :class:`PirnOpaqueValue`).
    """

    async def fetch_tag(
        self, tag: str, since: datetime
    ) -> AsyncIterator[Mapping[str, object]]:
        """Yield ``{timestamp, value}`` mappings for ``tag`` since ``since``."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement fetch_tag()"
        )

    async def close(self) -> None:
        """Close the underlying transport and release resources."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement close()"
        )
