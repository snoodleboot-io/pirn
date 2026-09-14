from __future__ import annotations

from typing import Any

from pirn.exceptions.pirn_error import PirnError


class HttpRetryableStatusError(PirnError):
    """A response whose status code asks the caller to retry (``429``, ``503``, ...).

    Raised inside one attempt of :meth:`pirn.connectors.http_connector.HttpConnector.request`
    so :meth:`pirn.core.knot_retry_policy.KnotRetryPolicy.run` can schedule the
    retry; when the policy stops retrying, the connector catches it and returns
    :attr:`response` — a retryable status is still a response, not a failure.

    Attributes:
        response: The backend response object (e.g. an ``httpx.Response``).
        status_code: Its HTTP status code.
    """

    def __init__(self, response: Any, status_code: int) -> None:
        super().__init__(f"HTTP {status_code} is retryable")
        self.response = response
        self.status_code = status_code
