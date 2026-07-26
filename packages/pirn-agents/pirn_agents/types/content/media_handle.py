"""``MediaHandle`` — a by-reference or inline pointer to binary media (F15-S1).

Image / audio / file content blocks do not embed their bytes in the message
graph; they carry a :class:`MediaHandle` that is *either*:

* a **reference** (:attr:`uri`) — an URL, blob-store key, or file path resolved
  lazily by whoever needs the bytes (a provider encoder, a renderer), or
* an **inline** payload (:attr:`data`) — the raw bytes, kept for small payloads
  that are cheaper to pass along than to re-fetch.

Exactly one of the two is set. The key property for pirn lineage is that raw
bytes never enter the content-addressed hash: :meth:`_pirn_audit_dict` emits an
*identity token* plus a size for inline data (reusing the opaque-value identity
keying) and the stable ``uri`` descriptor for references. Large payloads are
therefore passed by reference/handle and are never re-serialised through
lineage — matching the F15 performance requirement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class MediaHandle(PirnOpaqueValue):
    """A reference or inline pointer to one binary media payload.

    Attributes
    ----------
    media_type:
        The IANA media (MIME) type of the payload, e.g. ``"image/png"`` or
        ``"audio/wav"``.
    uri:
        A reference to the payload (URL, blob key, or path) resolved lazily;
        ``None`` when the payload is carried inline.
    data:
        The raw inline bytes; ``None`` when the payload is referenced by
        :attr:`uri`. Never serialised into lineage — see
        :meth:`_pirn_audit_dict`.
    """

    media_type: str
    uri: str | None = None
    data: bytes | None = None

    def __post_init__(self) -> None:
        """Validate types and that exactly one source (``uri``/``data``) is set.

        Raises:
            TypeError: If ``media_type`` is not a string, or ``uri``/``data``
                are of the wrong type.
            ValueError: If neither or both of ``uri`` and ``data`` are supplied.
        """
        if not isinstance(self.media_type, str) or not self.media_type:
            raise TypeError("MediaHandle: media_type must be a non-empty str")
        if self.uri is not None and not isinstance(self.uri, str):
            raise TypeError(
                f"MediaHandle: uri must be a str or None, got {type(self.uri).__name__}"
            )
        if self.data is not None and not isinstance(self.data, (bytes, bytearray)):
            raise TypeError(
                f"MediaHandle: data must be bytes or None, got {type(self.data).__name__}"
            )
        if (self.uri is None) == (self.data is None):
            raise ValueError("MediaHandle: exactly one of uri or data must be set")

    @property
    def is_inline(self) -> bool:
        """Return whether the payload is carried inline (bytes present)."""
        return self.data is not None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return an audit form that keeps raw bytes out of the content hash.

        Inline payloads emit an identity token (``<bytes@hex>``) plus a size, so
        two handles wrapping equal bytes stay identity-keyed and the bytes are
        never re-serialised through lineage; references emit their stable
        ``uri`` descriptor.
        """
        if self.data is not None:
            return {
                "media_type": self.media_type,
                "inline": f"<bytes@{id(self.data):x}>",
                "size": len(self.data),
            }
        return {"media_type": self.media_type, "uri": self.uri}
