"""Credential-safe base for connector configuration dataclasses.

Subclasses are produced by the
:func:`pirn.connectors.connection_config_decorator.connection_config`
decorator, which applies ``@dataclass(frozen=True, repr=False)`` so the
inherited :meth:`__repr__` wins over the dataclass-generated one. The
inherited repr redacts fields whose names look credential-bearing and
DSN-scrubs free string fields.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any, ClassVar

from pirn.connectors.dsn_scrubber import DsnScrubber


class ConnectionConfig:
    """Base class for connector configuration dataclasses.

    Apply :func:`connection_config` (preferred) or
    ``@dataclass(frozen=True, repr=False)`` (manual) to the subclass —
    ``repr=False`` is required because the redacting ``__repr__`` lives on
    this base class.

    Subclasses may declare additional sensitive-field names through
    :attr:`sensitive_fields` for fields whose names don't already contain a
    sensitivity keyword (e.g. ``signed_url``).
    """

    #: Field names matched as a substring (case-insensitive) to determine
    #: sensitivity. Defined as a class variable rather than a constant so it
    #: is treated as internal class configuration.
    _sensitive_name_patterns: ClassVar[tuple[str, ...]] = (
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "credentials",
        "credential",
        "passphrase",
        "private_key",
        "auth",
    )

    #: Subclasses may add field names that should be redacted even when the
    #: name itself does not contain a sensitivity keyword.
    sensitive_fields: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def _is_sensitive_name(cls, name: str) -> bool:
        lowered = name.lower()
        return any(pat in lowered for pat in cls._sensitive_name_patterns)

    def _is_sensitive_field(self, name: str) -> bool:
        return name in self.sensitive_fields or self._is_sensitive_name(name)

    @classmethod
    def _scrubber(cls) -> DsnScrubber:
        # Lazy per-class scrubber. Lives as a method (not a class attribute)
        # so we don't introduce a class-level constant.
        return DsnScrubber()

    def __repr__(self) -> str:
        if not is_dataclass(self):
            return object.__repr__(self)
        scrubber = self._scrubber()
        cls_name = type(self).__name__
        parts: list[str] = []
        for f in fields(self):
            value = getattr(self, f.name)
            if self._is_sensitive_field(f.name):
                shown: Any = "<redacted>"
            elif isinstance(value, str):
                shown = repr(scrubber.scrub(value))
            else:
                shown = repr(value)
            parts.append(f"{f.name}={shown}")
        return f"{cls_name}({', '.join(parts)})"

    def __str__(self) -> str:
        return self.__repr__()

    def to_audit_dict(self) -> dict[str, Any]:
        """Return an audit-safe dict — sensitive fields redacted, DSNs scrubbed."""
        if not is_dataclass(self):
            return {"_class": type(self).__name__}
        scrubber = self._scrubber()
        out: dict[str, Any] = {"_class": type(self).__name__}
        for f in fields(self):
            value = getattr(self, f.name)
            if self._is_sensitive_field(f.name):
                out[f.name] = "<redacted>"
            elif isinstance(value, str):
                out[f.name] = scrubber.scrub(value)
            else:
                out[f.name] = value
        return out
