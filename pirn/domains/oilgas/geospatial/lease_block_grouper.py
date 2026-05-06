"""``LeaseBlockGrouper`` — group well locations into lease blocks.

Algorithm:
    1. Receive a location dict and a ``lease_block_id`` string.
    2. Validate that ``lease_block_id`` is a non-empty string.
    3. Append ``lease_block_id`` to the location dict.
    4. Return the augmented location dict.


References:
    - BOEM (Bureau of Ocean Energy Management) Lease Block naming conventions,
      OCS Leasing and Operations (2023).
"""

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
        lease_block_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            location=location,
            lease_block_id=lease_block_id,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        location: dict[str, Any],
        lease_block_id: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Assign the lease_block_id to the location record and return it with the identifier appended.

        Args:
            location: Location dict to be tagged with the lease block identifier.
            lease_block_id: Non-empty lease block identifier string.

        Returns:
            Copy of the input location dict with ``lease_block_id`` added.
        """
        if not isinstance(lease_block_id, str) or not lease_block_id:
            raise ValueError(
                "LeaseBlockGrouper: lease_block_id must be a non-empty string"
            )
        return {
            **dict(location),
            "lease_block_id": lease_block_id,
        }
