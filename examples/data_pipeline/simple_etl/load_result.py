"""``LoadResult``

Part of the ``examples.data_pipeline.simple_etl`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoadResult:
    table: str
    rows_written: int
    db_path: str
