"""``DateDimGenerator`` — generate a complete date dimension table.

Generates rows for every calendar day in a given date range and writes
them to the target table. Each row has:

* ``date_key`` — integer in YYYYMMDD format (e.g. 20260101)
* ``full_date`` — ISO-8601 date string (e.g. "2026-01-01")
* ``year`` — 4-digit integer
* ``quarter`` — 1-4
* ``month`` — 1-12
* ``week`` — ISO week number (1-53)
* ``day_of_month`` — 1-31
* ``day_of_week`` — 1 (Monday) - 7 (Sunday) following ISO convention
* ``is_weekend`` — 1 if Saturday or Sunday, else 0
* ``fiscal_year`` — year for a fiscal calendar starting on
  ``fiscal_year_start_month`` (defaults to January, i.e. same as calendar
  year). When ``fiscal_year_start_month`` > 1 and the row's month falls on
  or after that month, the fiscal year is calendar_year + 1.

Algorithm:
    1. Receive resolved ``target_pool``, ``target_table``, ``start_date``,
       ``end_date``, and ``fiscal_year_start_month`` in ``process()``.
    2. Validate all inputs: pool type, non-empty string, identifier safety,
       date types, date ordering, and fiscal month range.
    3. Iterate one day at a time from ``start_date`` to ``end_date``
       inclusive.
    4. For each date compute all dimension columns and INSERT into the target
       table.
    5. Return a summary dict with ``succeeded``, ``target_table``, and
       ``rows_inserted``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

import datetime
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class DateDimGenerator(Knot):
    """Generate a complete date dimension for a given date range and write it to a target table."""

    def __init__(
        self,
        *,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        start_date: Knot | datetime.date,
        end_date: Knot | datetime.date,
        fiscal_year_start_month: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            target_pool=target_pool,
            target_table=target_table,
            start_date=start_date,
            end_date=end_date,
            fiscal_year_start_month=fiscal_year_start_month,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _insert_query(target_table: str) -> str:
        cols = (
            "date_key, full_date, year, quarter, month, week, "
            "day_of_month, day_of_week, is_weekend, fiscal_year"
        )
        placeholders = ", ".join(["?"] * 10)
        return f"INSERT INTO {target_table} ({cols}) VALUES ({placeholders})"

    @staticmethod
    def _fiscal_year(date: datetime.date, fiscal_year_start_month: int) -> int:
        if fiscal_year_start_month == 1:
            return date.year
        if date.month >= fiscal_year_start_month:
            return date.year + 1
        return date.year

    async def process(
        self,
        *,
        target_pool: Any,
        target_table: Any,
        start_date: Any,
        end_date: Any,
        fiscal_year_start_month: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("DateDimGenerator: target_pool must be a DatabaseConnectionPool")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("DateDimGenerator: target_table must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        if not isinstance(start_date, datetime.date):
            raise TypeError("DateDimGenerator: start_date must be a datetime.date")
        if not isinstance(end_date, datetime.date):
            raise TypeError("DateDimGenerator: end_date must be a datetime.date")
        if end_date < start_date:
            raise ValueError("DateDimGenerator: end_date must not precede start_date")
        if not isinstance(fiscal_year_start_month, int) or not (1 <= fiscal_year_start_month <= 12):
            raise ValueError(
                "DateDimGenerator: fiscal_year_start_month must be an integer in 1..12"
            )
        insert_q = self._insert_query(target_table)
        rows_inserted = 0
        current = start_date
        one_day = datetime.timedelta(days=1)
        while current <= end_date:
            iso_cal = current.isocalendar()
            date_key = current.year * 10000 + current.month * 100 + current.day
            quarter = (current.month - 1) // 3 + 1
            is_weekend = 1 if current.weekday() >= 5 else 0
            fy = self._fiscal_year(current, fiscal_year_start_month)
            await target_pool.execute(
                insert_q,
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
                    fy,
                ),
            )
            rows_inserted += 1
            current += one_day
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": rows_inserted,
        }
