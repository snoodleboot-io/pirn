"""``LeaseBlockGrouper`` — group well locations into lease blocks."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class LeaseBlockGrouper(Knot):
    """Assign a single location to a configured lease-block identifier."""

    def __init__(
        self,
        *,
        location: Knot,
        lease_block_id: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(lease_block_id, str) or not lease_block_id:
            raise ValueError(
                "LeaseBlockGrouper: lease_block_id must be a non-empty string"
            )
        self._lease_block_id = lease_block_id
        super().__init__(location=location, _config=_config, **kwargs)

    async def process(
        self, location: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        """Assign the configured lease_block_id to the location record and return it with the identifier appended.

        Args:
            location: Location dict to be tagged with the lease block identifier.

        Returns:
            Copy of the input location dict with ``lease_block_id`` added.
        """
        return {
            **dict(location),
            "lease_block_id": self._lease_block_id,
        }
