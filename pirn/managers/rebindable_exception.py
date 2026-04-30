from __future__ import annotations


class RebindableException(Exception):
    """Carrier for a placeholder record's identity when re-registering with
    the live ExceptionManager.

    A knot's __call__ may produce an Err with a placeholder ExceptionRecord
    (run_id="<unbound>") because the engine's manager was not in scope at
    raise time.  The engine constructs a RebindableException carrying the
    placeholder's exc_type and traceback_text, then passes it to
    ExceptionManager.record(), which produces a real record using those
    carried fields rather than re-deriving from the wrapper's own frames.
    """

    def __init__(
        self,
        exc_type: str,
        message: str,
        traceback_text: str,
    ) -> None:
        super().__init__(message)
        self.original_exc_type = exc_type
        self.original_traceback_text = traceback_text
