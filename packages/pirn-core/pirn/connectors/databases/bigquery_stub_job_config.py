"""Fallback ``QueryJobConfig`` substitute used when the real SDK is absent.

Tests inject their own BigQuery client and may not have
``google-cloud-bigquery`` installed; this lightweight stand-in preserves
``query_parameters`` so the stub can inspect them without making the real
SDK a test dependency.
"""

from __future__ import annotations

from typing import Any


class BigqueryStubJobConfig:
    """Minimal substitute exposing ``query_parameters`` only."""

    def __init__(self, query_parameters: list[Any]) -> None:
        self.query_parameters = query_parameters
