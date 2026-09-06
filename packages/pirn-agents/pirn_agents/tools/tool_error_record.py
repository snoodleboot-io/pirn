"""``ToolErrorRecord`` — capture a failed tool call without leaking credentials.

A tool's exception message routinely carries whatever it was talking to. A SQL
tool reports the DSN it could not reach; an MCP tool reports the server URL it
could not reach. :class:`~pirn.managers.exception_record.ExceptionRecord` does
no redaction of its own, so capturing one verbatim writes those credentials into
``ToolResult.error`` and into the record that persists to lineage and history.

Every tool-invocation path needs the same treatment, and until PIR-733 they did
not get it: ``ToolExecutor`` scrubbed, while ``ParallelToolExecutor``,
``ToolChain`` and ``McpTool`` each captured the raw record. This class exists so
there is one implementation rather than four opportunities to forget — the
inconsistency is what let the batch path leak while the single-call path did not.

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
    def scrubbed(cls, tool_name: str, exc: BaseException) -> ExceptionRecord:
        """Return an :class:`ExceptionRecord` for ``exc`` with credentials redacted.

        Args:
            tool_name: Name of the tool that failed; recorded as the knot id.
            exc: The exception raised by the tool.

        Returns:
            A record whose ``message`` and ``traceback_text`` have both been
            passed through :class:`~pirn.connectors.dsn_scrubber.DsnScrubber`.
        """
        raw = ExceptionRecord.for_knot(tool_name, exc)
        return raw.model_copy(
            update={
                "message": cls._scrubber.scrub(raw.message),
                "traceback_text": cls._scrubber.scrub(raw.traceback_text),
            }
        )

    @classmethod
    def scrubbed_message(cls, exc: BaseException) -> str:
        """Return ``"TypeName: <scrubbed message>"`` for a ``ToolResult.error``.

        Args:
            exc: The exception raised by the tool.

        Returns:
            The conventional error string, with credentials redacted.
        """
        return f"{type(exc).__name__}: {cls._scrubber.scrub(str(exc))}"
