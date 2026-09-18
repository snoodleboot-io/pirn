"""``AuthToken`` — a verified bearer token and its scopes.

Part of the ``examples.software_execution.request_handler`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AuthToken:
    user_id: str
    scopes: list
