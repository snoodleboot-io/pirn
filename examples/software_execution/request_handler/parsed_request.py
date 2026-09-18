"""``ParsedRequest`` — an inbound HTTP request after parsing.

Part of the ``examples.software_execution.request_handler`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedRequest:
    path: str
    method: str
    headers: dict
    body: dict
