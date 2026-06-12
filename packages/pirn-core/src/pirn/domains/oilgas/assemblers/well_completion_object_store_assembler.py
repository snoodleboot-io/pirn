"""``WellCompletionObjectStoreAssembler`` — assemble a :class:`DrillingParameters` from completion bytes.

Sits between :class:`~pirn.connectors.knots.object_store_read_source.ObjectStoreReadSource`
(which produces ``bytes``) and downstream completion analysis knots that consume
:class:`~pirn.domains.oilgas.types.drilling_parameters.DrillingParameters`.

The raw bytes encode a JSON completion record with perforation intervals,
packer depths, and sliding sleeve positions.

References:
    - API RP 19D (2008) — Measuring the Properties of Proppants.
    - Economides & Nolte (2000). Reservoir Stimulation, 3rd ed., Chapter 5.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.drilling_parameters import DrillingParameters


class WellCompletionObjectStoreAssembler(Assembler):
    """Assemble a :class:`DrillingParameters` from raw completion record bytes."""

    def __init__(
        self,
        *,
        body: Knot,
        well_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(body=body, well_id=well_id, _config=_config, **kwargs)

    async def process(
        self,
        body: bytes,
        well_id: str,
        **_: Any,
    ) -> DrillingParameters:
        """Decode raw completion record bytes into a :class:`DrillingParameters`.

        Args:
            body: Raw JSON bytes encoding the completion record.
            well_id: Non-empty well identifier string.

        Returns:
            :class:`DrillingParameters` with ``depth_count`` derived from
            the perforation interval count in the completion record.

        Raises:
            TypeError: If ``body`` is not ``bytes`` or ``well_id`` is not ``str``.
            ValueError: If ``well_id`` is empty or ``body`` is not valid JSON.
        """
        if not isinstance(body, bytes):
            raise TypeError(
                f"WellCompletionObjectStoreAssembler: body must be bytes, got {type(body).__name__}"
            )
        if not isinstance(well_id, str):
            raise TypeError(
                f"WellCompletionObjectStoreAssembler: well_id must be str, got {type(well_id).__name__}"
            )
        if not well_id:
            raise ValueError("WellCompletionObjectStoreAssembler: well_id must be non-empty")
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"WellCompletionObjectStoreAssembler: body is not valid JSON: {exc}"
            ) from exc
        if isinstance(data, dict):
            perforations = data.get("perforations", data.get("intervals", []))
            depth_count = len(perforations) if isinstance(perforations, list) else max(1, len(data))
        elif isinstance(data, list):
            depth_count = len(data)
        else:
            depth_count = 1
        return DrillingParameters(
            well_id=well_id,
            depth_count=depth_count,
            fetched_at=datetime.now(UTC),
        )
