"""``MudLogAssembler`` — assemble a structured mud log dict from raw JSON bytes.

Sits between :class:`~pirn.connectors.knots.object_store_read_source.ObjectStoreReadSource`
(which produces ``bytes``) and downstream mud-log analysis knots.

The decoded dict carries well name, record count, curve list, and data rows.
Mud log data does not yet have a typed Payload in the oilgas domain; this
assembler bridges the connector boundary until one is introduced.

References:
    - IADC Mud Logging Manual (1999), Section 3.
"""

from __future__ import annotations

import json
from typing import Any

from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class MudLogAssembler(Assembler):
    """Assemble a structured mud log dict from raw JSON bytes."""

    def __init__(
        self,
        *,
        body: Knot,
        required_curves: Knot | tuple[str, ...] = ("depth_ft", "rop_ft_hr", "gas_units"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            body=body,
            required_curves=required_curves,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        body: bytes,
        required_curves: tuple[str, ...] = ("depth_ft", "rop_ft_hr", "gas_units"),
        **_: Any,
    ) -> dict[str, Any]:
        """Decode raw mud log JSON bytes into a structured dict.

        Args:
            body: Raw JSON bytes encoding a dict with ``header`` and ``data``
                keys. ``data`` is a list of row dicts keyed by curve mnemonic.
            required_curves: Curve names that must appear in every data row.

        Returns:
            Dict with ``well_name`` (str), ``record_count`` (int),
            ``curves`` (list[str]), and ``data`` (list[dict]).

        Raises:
            TypeError: If ``body`` is not ``bytes``.
            ValueError: If required fields or curves are missing from the payload.
        """
        if not isinstance(body, bytes):
            raise TypeError(f"MudLogAssembler: body must be bytes, got {type(body).__name__}")
        try:
            raw: dict[str, Any] = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError(f"MudLogAssembler: body is not valid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError(
                f"MudLogAssembler: decoded JSON must be a dict, got {type(raw).__name__}"
            )
        for field in ("data", "header"):
            if field not in raw:
                raise ValueError(
                    f"MudLogAssembler: missing required field '{field}'; got: {list(raw)}"
                )
        data: list[dict[str, Any]] = raw["data"]
        header: dict[str, Any] = raw["header"]
        if data:
            first_row_keys = set(data[0].keys())
            missing = [c for c in required_curves if c not in first_row_keys]
            if missing:
                raise ValueError(f"MudLogAssembler: missing required curves: {missing}")
        curves = list(data[0].keys()) if data else list(required_curves)
        return {
            "well_name": header.get("well_name", "unknown"),
            "record_count": len(data),
            "curves": curves,
            "data": data,
        }
