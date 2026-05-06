"""``PSVTestRecordParser`` — parse pressure safety valve test records.

Algorithm:
    1. Receive a ``raw_record`` dict and ``required_fields`` tuple.
    2. Validate that ``raw_record`` is a dict and all required fields are present.
    3. Return the record with a ``parsed: True`` flag appended.


References:
    - API RP 576 (4th ed., 2017) — Inspection of Pressure-Relieving Devices.
    - ASME PTC 25-2018 — Pressure Relief Devices, Performance Test Codes.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class PSVTestRecordParser(Knot):
    """Parse a PSV test record and validate required fields are present."""

    def __init__(
        self,
        *,
        raw_record: Knot,
        required_fields: Knot | tuple[str, ...] = (
            "tag",
            "set_pressure_psi",
            "test_date",
            "pass_fail",
        ),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            raw_record=raw_record,
            required_fields=required_fields,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        raw_record: dict[str, Any],
        required_fields: tuple[str, ...] = (
            "tag",
            "set_pressure_psi",
            "test_date",
            "pass_fail",
        ),
        **_: Any,
    ) -> dict[str, Any]:
        """Parse PSV test record and return validated output with ``parsed`` flag.

        Args:
            raw_record: Dict containing PSV test fields; must include all
                ``required_fields``.
            required_fields: Tuple of field names that must be present in the record.

        Returns:
            Dict containing all input keys plus ``parsed: True``.
        """
        if not isinstance(raw_record, dict):
            raise TypeError("PSVTestRecordParser: raw_record must be a dict")
        missing = [f for f in required_fields if f not in raw_record]
        if missing:
            raise ValueError(f"PSVTestRecordParser: missing required fields: {missing}")
        return {**raw_record, "parsed": True}
