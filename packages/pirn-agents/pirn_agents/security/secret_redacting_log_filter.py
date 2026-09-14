"""``SecretRedactingLogFilter`` — scrub secrets out of log records before they emit.

A :class:`logging.Filter` that runs every record's fully-formatted message
through a :class:`~pirn_agents.security.secret_leak_scanner.SecretLeakScanner`
and, when a secret is found, rewrites the record so the handler only ever writes
the redacted form. This closes the "logs" surface of F11-S6: the previously
unprotected log emitters now redact detected secrets *before* writing, without
any change at the call sites.

Attach it to a logger or handler with ``logger.addFilter(SecretRedactingLogFilter())``,
or with :meth:`SecretRedactingLogFilter.install` for the common case of the
whole ``pirn_agents`` package logger.
"""

from __future__ import annotations

import logging

from pirn_agents.security.secret_leak_scanner import SecretLeakScanner


class SecretRedactingLogFilter(logging.Filter):
    """Redact secrets in a log record's message before it is emitted."""

    @classmethod
    def install(
        cls, *, logger_name: str = "pirn_agents", scanner: SecretLeakScanner | None = None
    ) -> SecretRedactingLogFilter:
        """Attach a redacting filter to ``logging.getLogger(logger_name)``.

        Idempotent: if ``logger_name`` already carries a filter of this class
        it is returned unchanged rather than stacking a second one — calling
        this more than once (e.g. from more than one import path) is safe.
        This is opt-in, not automatic on import: nothing in this package calls
        it for you, since attaching a regex-scanning filter to a logger is a
        deployment decision (see the WS2 report — the one-line hookup for the
        application/bootstrap layer is ``SecretRedactingLogFilter.install()``).

        Args:
            logger_name: The logger to attach to; defaults to the package
                logger every ``pirn_agents`` module logs under.
            scanner: The scanner to reuse; a default one is built when
                ``None``.

        Returns:
            The installed (or already-present) filter instance.
        """
        logger = logging.getLogger(logger_name)
        for existing in logger.filters:
            if isinstance(existing, cls):
                return existing
        installed = cls(scanner=scanner)
        logger.addFilter(installed)
        return installed

    def __init__(self, *, scanner: SecretLeakScanner | None = None, name: str = "") -> None:
        """Configure the filter.

        Args:
            scanner: The scanner to reuse; a default one is built when ``None``.
            name: Optional logger-name filter forwarded to :class:`logging.Filter`.

        Raises:
            TypeError: If ``scanner`` is not a :class:`SecretLeakScanner`.
        """
        super().__init__(name)
        if scanner is not None and not isinstance(scanner, SecretLeakScanner):
            raise TypeError("SecretRedactingLogFilter: scanner must be a SecretLeakScanner")
        self._scanner = scanner if scanner is not None else SecretLeakScanner()

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the record's rendered message in place, then allow it through.

        The record's ``args`` are folded into ``msg`` (via
        :meth:`logging.LogRecord.getMessage`) and cleared, so the substituted,
        redacted text is what any handler formats — no secret survives in the
        unexpanded ``%s`` arguments either.
        """
        rendered = record.getMessage()
        redacted, kinds = self._scanner.redact_text(rendered)
        if kinds:
            record.msg = redacted
            record.args = None
        return True
