"""``UsersSnapshot`` — one day of user activity counts from the user service.

Part of the ``examples.data_pipeline.complex_analytics`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UsersSnapshot:
    date: str
    active_users: int
    new_users: int
