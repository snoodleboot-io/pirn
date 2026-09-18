"""``Account`` — the caller's billing account and remaining quota.

Part of the ``examples.software_execution.request_handler`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Account:
    account_id: str
    plan: str
    quota_remaining: int
