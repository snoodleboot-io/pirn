"""``UserProfile`` — the caller's profile as fetched from the user service.

Part of the ``examples.software_execution.request_handler`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UserProfile:
    user_id: str
    name: str
    email: str
