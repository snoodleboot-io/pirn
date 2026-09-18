"""``MudLogAssembler`` — assemble a :class:`MudLogPayload` from raw JSON bytes.

Sits between :class:`~pirn.connectors.knots.object_store_read_source.ObjectStoreReadSource`
(which produces ``bytes``) and downstream mud-log analysis knots.

Algorithm:
    1. Receive ``body`` (raw JSON bytes) and ``required_curves``.
    2. Validate that ``body`` is ``bytes`` and decodes to a JSON dict with
       ``header`` and ``data`` keys.
    3. Validate every record, not only the first: each is a mapping carrying
       every name in ``required_curves``, every value is a number or a string
       (a nested object or array is not a curve reading), and every record has
       the same curve set — a log whose rows disagree is a decode error, not a
       row to pass on.
    4. Derive ``curves`` from the records (or from ``required_curves`` when the
       log is empty).
    5. Return a :class:`MudLogPayload` carrying the records and a
       :class:`~pirn_oilgas.types.mud_log.MudLog` built from the header.

References:
    - IADC Mud Logging Manual (1999), Section 3.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.shape_guard import ShapeGuard

from pirn_oilgas.types.mud_log import MudLog
from pirn_oilgas.types.mud_log_payload import MudLogPayload


class MudLogAssembler(Assembler):
    """Assemble a :class:`MudLogPayload` from raw mud log JSON bytes."""

    def __init__(
        self,
        *,
        body: Knot,
        required_curves: Knot | tuple[str, ...] = ("depth_ft", "rop_ft_hr", "gas_units"),
        depth_unit: Knot | str = "ft",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            body=body,
            required_curves=required_curves,
            depth_unit=depth_unit,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        body: bytes,
        required_curves: tuple[str, ...] = ("depth_ft", "rop_ft_hr", "gas_units"),
        depth_unit: str = "ft",
        **_: Any,
    ) -> MudLogPayload:
        """Decode raw mud log JSON bytes into a :class:`MudLogPayload`.

        Args:
            body: Raw JSON bytes encoding a dict with ``header`` and ``data``
                keys. ``data`` is a list of row dicts keyed by curve mnemonic.
            required_curves: Curve names that must appear in every data row.
            depth_unit: Depth unit of the log; must be ``'ft'`` or ``'m'``.

        Returns:
            :class:`MudLogPayload` whose ``data`` is the tuple of decoded records
            and whose ``metadata`` names the well, its curves and its record count.

        Raises:
            TypeError: If ``body`` is not ``bytes``.
            ValueError: If the payload is not valid JSON, a required field or curve
                is missing, ``depth_unit`` is not ``'ft'`` or ``'m'``, or a record
                is malformed.
        """
        if not isinstance(body, bytes):
            raise TypeError(f"MudLogAssembler: body must be bytes, got {type(body).__name__}")
        if depth_unit not in ("ft", "m"):
            raise ValueError("MudLogAssembler: depth_unit must be 'ft' or 'm'")
        try:
            decoded: object = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError(f"MudLogAssembler: body is not valid JSON: {exc}") from exc
        if not ShapeGuard.is_str_keyed_dict(decoded):
            raise ValueError(
                f"MudLogAssembler: decoded JSON must be a dict, got {type(decoded).__name__}"
            )
        for field_name in ("data", "header"):
            if field_name not in decoded:
                raise ValueError(
                    f"MudLogAssembler: missing required field '{field_name}'; got: {list(decoded)}"
                )
        header = decoded["header"]
        if not ShapeGuard.is_str_keyed_dict(header):
            raise ValueError(
                f"MudLogAssembler: 'header' must be a dict, got {type(header).__name__}"
            )
        rows = decoded["data"]
        if not ShapeGuard.is_list(rows):
            raise ValueError(f"MudLogAssembler: 'data' must be a list, got {type(rows).__name__}")
        records = self._records(rows, required_curves)
        curves = tuple(records[0]) if records else tuple(required_curves)
        return MudLogPayload(
            metadata=MudLog(
                well_name=str(header.get("well_name", "unknown")),
                curves=curves,
                record_count=len(records),
                depth_unit=depth_unit,
                fetched_at=datetime.now(UTC),
            ),
            data=records,
        )

    @staticmethod
    def _records(
        rows: list[object], required_curves: tuple[str, ...]
    ) -> tuple[Mapping[str, float | str], ...]:
        """Validate and normalise every decoded row into a typed record.

        Args:
            rows: The decoded ``data`` list.
            required_curves: Curve names every record must carry.

        Returns:
            One immutable mapping per record, values narrowed to ``float`` or ``str``.

        Raises:
            ValueError: If a row is not a string-keyed mapping, a required curve is missing from
                any row, a value is neither a number nor a string, or the rows do
                not all carry the same curves.
        """
        records: list[Mapping[str, float | str]] = []
        first_curves: tuple[str, ...] | None = None
        for index, row in enumerate(rows):
            if not ShapeGuard.is_str_keyed_dict(row):
                raise ValueError(
                    f"MudLogAssembler: record {index} must be a dict, got {type(row).__name__}"
                )
            missing = [curve for curve in required_curves if curve not in row]
            if missing:
                raise ValueError(
                    f"MudLogAssembler: missing required curves: {missing} in record {index}"
                )
            record: dict[str, float | str] = {}
            for name, value in row.items():
                if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                    raise ValueError(
                        f"MudLogAssembler: curve {name!r} in record {index} is "
                        f"{type(value).__name__}, not a number or a string"
                    )
                record[name] = value if isinstance(value, str) else float(value)
            curves = tuple(record)
            if first_curves is None:
                first_curves = curves
            elif curves != first_curves:
                raise ValueError(
                    f"MudLogAssembler: record {index} carries curves {list(curves)}, but "
                    f"record 0 carries {list(first_curves)} — the log is not uniform"
                )
            records.append(record)
        return tuple(records)
