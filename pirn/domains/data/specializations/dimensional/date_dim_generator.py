"""``DateDimGenerator`` — Generate a complete date dimension table.

Generates rows for every calendar day in a given date range and writes
them to the target table. Each row has:

* ``date_key`` — integer in YYYYMMDD format (e.g. 20260101)
* ``full_date`` — ISO-8601 date string (e.g. "2026-01-01")
* ``year`` — 4-digit integer
* ``quarter`` — 1–4
* ``month`` — 1–12
* ``week`` — ISO week number (1–53)
* ``day_of_month`` — 1–31
* ``day_of_week`` — 1 (Monday) – 7 (Sunday) following ISO convention
* ``is_weekend`` — 1 if Saturday or Sunday, else 0
* ``fiscal_year`` — year for a fiscal calendar starting on
  ``fiscal_year_start_month`` (defaults to January, i.e. same as calendar
  year). When ``fiscal_year_start_month`` > 1 and the row's month falls on
  or after that month, the fiscal year is calendar_year + 1.
"""

from __future__ import annotations

import datetime
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class DateDimGenerator(SubTapestry):
    """Generate a complete date dimension for a given date range and write it to a target table."""

    def __init__(
        self,
        *,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        start_date: datetime.date,
        end_date: datetime.date,
        fiscal_year_start_month: int = 1,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "DateDimGenerator: target_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_table, str) or not target_table:
            raise ValueError(
                "DateDimGenerator: target_table must be a non-empty string"
            )
        IdentifierValidator.validate_column("target_table", target_table)
        if not isinstance(start_date, datetime.date):
            raise TypeError(
                "DateDimGenerator: start_date must be a datetime.date"
            )
        if not isinstance(end_date, datetime.date):
            raise TypeError(
                "DateDimGenerator: end_date must be a datetime.date"
            )
        if end_date < start_date:
            raise ValueError(
                "DateDimGenerator: end_date must not precede start_date"
            )
        if not isinstance(fiscal_year_start_month, int) or not (
            1 <= fiscal_year_start_month <= 12
        ):
            raise ValueError(
                "DateDimGenerator: fiscal_year_start_month must be an integer in 1..12"
            )
        self._target_pool = target_pool
        self._target_table = target_table
        self._start_date = start_date
        self._end_date = end_date
        self._fiscal_year_start_month = fiscal_year_start_month
        super().__init__(_config=_config, **kwargs)

    @property
    def insert_query(self) -> str:
        cols = (
            "date_key, full_date, year, quarter, month, week, "
            "day_of_month, day_of_week, is_weekend, fiscal_year"
        )
        placeholders = ", ".join(["?"] * 10)
        return (
            f"INSERT INTO {self._target_table} ({cols}) "
            f"VALUES ({placeholders})"
        )

    def _fiscal_year(self, d: datetime.date) -> int:
        if self._fiscal_year_start_month == 1:
            return d.year
        if d.month >= self._fiscal_year_start_month:
            return d.year + 1
        return d.year

    async def process(self, **_: Any) -> dict[str, Any]:
        """Generate one row per calendar day in the configured range and insert into the target table.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, and ``rows_inserted``
            summarising the outcome.
        """
        rows_inserted = 0
        current = self._start_date
        one_day = datetime.timedelta(days=1)
        while current <= self._end_date:
            iso_cal = current.isocalendar()
            date_key = current.year * 10000 + current.month * 100 + current.day
            quarter = (current.month - 1) // 3 + 1
            is_weekend = 1 if current.weekday() >= 5 else 0
            fiscal_year = self._fiscal_year(current)
            await self._target_pool.execute(
                self.insert_query,
                (
                    date_key,
                    current.isoformat(),
                    current.year,
                    quarter,
                    current.month,
                    iso_cal[1],
                    current.day,
                    iso_cal[2],
                    is_weekend,
                    fiscal_year,
                ),
            )
            rows_inserted += 1
            current += one_day
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_inserted": rows_inserted,
        }
