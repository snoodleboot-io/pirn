# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``WellCompletionObjectStoreAssembler`` — assemble a :class:`DrillingParameters` from completion bytes.

Sits between :class:`~pirn.connectors.knots.object_store_read_source.ObjectStoreReadSource`
(which produces ``bytes``) and downstream completion analysis knots that consume
:class:`~pirn_oilgas.types.drilling_parameters.DrillingParameters`.

The raw bytes encode a JSON completion record with perforation intervals,
packer depths, and sliding sleeve positions.

Algorithm:
    1. Receive ``body`` (raw JSON bytes) and ``well_id``.
    2. Validate that ``body`` is ``bytes``, ``well_id`` is a non-empty
       string, and ``body`` decodes as JSON.
    3. Derive ``depth_count``:

       - decoded dict with a list under ``perforations`` or ``intervals``
         → the length of that list;
       - decoded dict without either key → ``max(1, len(dict))``;
       - decoded list → its length;
       - anything else → ``1``.
    4. Return a :class:`DrillingParameters` with ``well_id``,
       ``depth_count``, and the current UTC timestamp as ``fetched_at``.

References:
    - API RP 19D (2008) — Measuring the Properties of Proppants.
    - Economides & Nolte (2000). Reservoir Stimulation, 3rd ed., Chapter 5.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, TypeGuard

from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.drilling_parameters import DrillingParameters


class WellCompletionObjectStoreAssembler(Assembler):
    """Assemble a :class:`DrillingParameters` from raw completion record bytes."""

    @staticmethod
    def _is_json_object(value: object) -> TypeGuard[dict[str, object]]:
        """Whether a ``json.loads`` result is a JSON object (always string-keyed)."""
        return isinstance(value, dict)

    @staticmethod
    def _is_json_array(value: object) -> TypeGuard[list[object]]:
        """Whether a ``json.loads`` result is a JSON array."""
        return isinstance(value, list)

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
        if WellCompletionObjectStoreAssembler._is_json_object(data):
            perforations = data.get("perforations", data.get("intervals", []))
            if WellCompletionObjectStoreAssembler._is_json_array(perforations):
                depth_count = len(perforations)
            else:
                depth_count = max(1, len(data))
        elif WellCompletionObjectStoreAssembler._is_json_array(data):
            depth_count = len(data)
        else:
            depth_count = 1
        return DrillingParameters(
            well_id=well_id,
            depth_count=depth_count,
            fetched_at=datetime.now(UTC),
        )
