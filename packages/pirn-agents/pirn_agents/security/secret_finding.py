"""``SecretFinding`` — a single detected secret, without the secret itself.

A frozen record naming *what kind* of secret was found (``"dsn"``, ``"aws_key"``,
``"jwt"``, ``"private_key"``, ``"authorization"``, ``"assignment"``, or
``"secret_key_name"``) and *where* (a dotted ``path`` such as ``"args.password"``
or ``"result.items[0]"``). It deliberately never stores the matched secret, so a
findings list is safe to log or return.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SecretFinding(PirnOpaqueValue):
    """Immutable, secret-free record of one redaction.

    Attributes
    ----------
    kind:
        The class of secret detected.
    path:
        Dotted location within the scanned structure (``"text"`` for a bare
        string scan).
    """

    kind: str
    path: str

    def __post_init__(self) -> None:
        """Validate the field types.

        Raises
        ------
        TypeError
            If ``kind`` or ``path`` is not a string.
        ValueError
            If ``kind`` is empty.
        """
        if not isinstance(self.kind, str) or not isinstance(self.path, str):
            raise TypeError("SecretFinding: kind and path must be strings")
        if not self.kind:
            raise ValueError("SecretFinding: kind must be non-empty")

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return a stable content-addressing view of the finding."""
        return {"kind": self.kind, "path": self.path}
