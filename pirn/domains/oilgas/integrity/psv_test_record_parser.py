"""``PSVTestRecordParser`` — parse pressure safety valve test records."""

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
        required_fields: tuple[str, ...] = (
            "tag",
            "set_pressure_psi",
            "test_date",
            "pass_fail",
        ),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._required_fields = required_fields
        super().__init__(raw_record=raw_record, _config=_config, **kwargs)

    async def process(self, raw_record: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Parse PSV test record and return validated output with ``parsed`` flag.

        Args:
            raw_record: Dict containing PSV test fields; must include all
                configured ``required_fields``.

        Returns:
            Dict containing all input keys plus ``parsed: True``.
        """
        if not isinstance(raw_record, dict):
            raise TypeError("PSVTestRecordParser: raw_record must be a dict")
        missing = [f for f in self._required_fields if f not in raw_record]
        if missing:
            raise ValueError(
                f"PSVTestRecordParser: missing required fields: {missing}"
            )
        return {**raw_record, "parsed": True}
