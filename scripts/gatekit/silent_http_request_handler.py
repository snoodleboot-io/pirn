"""``SilentHttpRequestHandler`` — a static file handler that logs nothing."""

from __future__ import annotations

import http.server
from typing import Any


class SilentHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    """``SimpleHTTPRequestHandler`` with request logging suppressed."""

    def log_message(self, format: str, *args: Any) -> None:
        """Drop the per-request log line ``SimpleHTTPRequestHandler`` writes to stderr."""
