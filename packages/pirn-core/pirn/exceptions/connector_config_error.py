from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class ConnectorConfigError(PirnError, RuntimeError):
    """Raised when a connector's configuration cannot satisfy the call.

    Covers both halves of "the connector was never told enough to do this":
    neither an explicit config nor an injected client at all, and a config
    present but missing the field this particular call needs (a ``base_url``,
    an ``api_key``, the query a paging adapter pages over).

    Subclasses ``RuntimeError`` in addition to ``PirnError`` so every
    existing ``except RuntimeError`` handler around a connector call keeps
    working unchanged, while new code can narrow to this specific failure.
    """
