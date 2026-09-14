"""``PromptRenderError`` — raised when a template cannot be rendered safely."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class PromptRenderError(PirnError, ValueError):
    """A prompt template could not be rendered.

    Raised for missing required variables, unresolved placeholders, unknown
    partial references, or values/names that fail the injection-safety
    validation. Subclasses :class:`ValueError` so existing callers that catch
    ``ValueError`` around rendering keep working.
    """
