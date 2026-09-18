"""``ApiResponse`` — the status, body and latency of the handled request.

Part of the ``examples.software_execution.request_handler`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ApiResponse:
    status: int
    body: dict
    duration_ms: float
