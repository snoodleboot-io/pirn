"""``TrajectoryCallKey`` — stable, order-independent key for a step's arguments."""

from __future__ import annotations

import json


class TrajectoryCallKey:
    """Build a stable JSON key from a trajectory step's arguments."""

    def args_key(self, arguments: object) -> str:
        """Return a stable, order-independent key for a step's arguments."""
        return json.dumps(arguments, sort_keys=True, default=str)
