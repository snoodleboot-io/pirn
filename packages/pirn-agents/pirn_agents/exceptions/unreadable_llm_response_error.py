"""``UnreadableLlmResponseError`` — a chat completion carried no readable text."""

from __future__ import annotations

from pirn.core.shape_guard import ShapeGuard
from pirn.exceptions.pirn_error import PirnError


class UnreadableLlmResponseError(PirnError, TypeError):
    """Raised when a provider response matches no known chat-completion shape.

    Subclasses :class:`~pirn.exceptions.pirn_error.PirnError` in addition to
    ``TypeError`` so the existing ``except TypeError`` handlers around text
    extraction keep working, while new code can narrow to ``PirnError``.

    Extraction used to end in ``return str(raw)``, which is why this exists: a
    response the normaliser did not understand was handed on as if it were the
    model's answer, so a knot returned ``"{'error': ...}"`` as a RAG answer, or
    split a Python repr into "facts" and wrote them to long-term memory. An
    unreadable response is a failure of the provider or of the shape this code
    knows, and it fails the knot rather than fabricating a value.

    Attributes
    ----------
    response_type:
        Name of the type that could not be read.
    keys:
        The response's top-level keys when it was a mapping, else ``()`` — the
        actionable part of the diagnosis, and the part that is safe to log
        (the values may carry untrusted model output).
    """

    def __init__(self, raw: object) -> None:
        self.response_type = type(raw).__name__
        self.keys: tuple[str, ...] = (
            tuple(str(key) for key in raw) if ShapeGuard.is_mapping(raw) else ()
        )
        detail = f" with keys {list(self.keys)!r}" if self.keys else ""
        super().__init__(
            f"no readable text in a chat completion of type "
            f"{self.response_type}{detail}; expected a str, a mapping with a "
            f"str 'content' or 'text', or a non-empty content block list"
        )
