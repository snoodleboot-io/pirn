"""Traceback redaction of common credential patterns.

``redact_common_secrets`` (a bare alias for
:meth:`_TracebackRedactor.redact_common_secrets`) is the ``traceback_filter``
to pass to ``ExceptionManager`` or ``Tapestry`` to reduce the risk of
credentials appearing in stored exception records.
"""

from __future__ import annotations

import re as _re


class _TracebackRedactor:
    """Regex-based redaction of credential-looking text in tracebacks."""

    @staticmethod
    def redact_common_secrets(text: str) -> str:
        """Replace common credential patterns in a traceback with <redacted>.

        Patterns matched:

        * DSN credentials: ``postgresql://user:pass@host`` → ``postgresql://<redacted>@host``
        * Named credential assignments: ``password=s3cr3t``, ``api_key=xyz``, etc.
        * Authorization header values: ``Authorization: Bearer <token>``
        """
        text = _re.sub(r'(://)[^@\s"\']+(@)', r"\1<redacted>\2", text)
        text = _re.sub(
            r"(?i)\b(password|passwd|api_?key|token|secret|auth)\s*[=:]\s*\S+",
            r"\1=<redacted>",
            text,
        )
        text = _re.sub(r"(?i)(Authorization:\s*\w+\s+)\S+", r"\1<redacted>", text)
        return text


#: Public name for :meth:`_TracebackRedactor.redact_common_secrets` (bare alias).
redact_common_secrets = _TracebackRedactor.redact_common_secrets
