"""``ToolErrorRecord`` — capture a failed tool call without leaking credentials.

A tool's exception message routinely carries whatever it was talking to. A SQL
tool reports the DSN it could not reach; an MCP tool reports the server URL it
could not reach. :class:`~pirn.managers.exception_record.ExceptionRecord` does
no redaction of its own, and core's ``traceback_filter`` seam
(``Tapestry(traceback_filter=...)``) reaches only ``traceback_text`` — never
``message`` — so a record captured verbatim writes the credential into the
``Err`` every consumer reads and into the row that persists to history.

This class is the one place tool records are scrubbed.  Since the ADR
"agents speaks core" (WS1) made a tool a knot, :meth:`scrubbed_record` runs on
the tool knot's own ``__call__`` for every ``Err`` it produces, so every
invocation path — the engine, a fan-out, ``ToolFactory.run_call`` — is
covered by construction rather than by each executor remembering to call it.
The engine's re-registration of a placeholder record preserves the scrubbed
``message`` and ``traceback_text`` (it re-registers through
``RebindableError``, which carries both), so what leaves the knot is what
lands in lineage.

Two details that are easy to get wrong, both encoded here:

* The record carries the message **twice** — in ``message`` and again inside
  ``traceback_text``, which is the formatted exception. Scrubbing only the
  former still persists the credential.
* The exception object is never reconstructed. ``type(exc)(scrubbed)`` fails for
  any exception whose constructor takes more than a message, and it would fail
  inside an ``except`` block, turning a redaction step into a crash. Copying the
  frozen record sidesteps that entirely.
"""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.managers.exception_record import ExceptionRecord


class ToolErrorRecord:
    """Builds credential-safe :class:`ExceptionRecord`s for failed tool calls."""

    _scrubber: ClassVar[DsnScrubber] = DsnScrubber()

    @classmethod
    def scrubbed_record(cls, record: ExceptionRecord) -> ExceptionRecord:
        """Return a copy of *record* with credentials redacted from message and traceback."""
        return record.model_copy(
            update={
                "message": cls._scrubber.scrub(record.message),
                "traceback_text": cls._scrubber.scrub(record.traceback_text),
            }
        )

    @classmethod
    def scrubbed(cls, tool_name: str, exc: BaseException) -> ExceptionRecord:
        """Return an :class:`ExceptionRecord` for ``exc`` with credentials redacted.

        Args:
            tool_name: Name of the tool that failed; recorded as the knot id.
            exc: The exception raised by the tool.

        Returns:
            A record whose ``message`` and ``traceback_text`` have both been
            passed through :class:`~pirn.connectors.dsn_scrubber.DsnScrubber`.
        """
        return cls.scrubbed_record(ExceptionRecord.for_knot(tool_name, exc))

    @classmethod
    def scrubbed_message(cls, exc: BaseException) -> str:
        """Return ``"TypeName: <scrubbed message>"`` for a ``ToolResult.error``.

        Args:
            exc: The exception raised by the tool.

        Returns:
            The conventional error string, with credentials redacted.
        """
        return f"{type(exc).__name__}: {cls._scrubber.scrub(str(exc))}"
