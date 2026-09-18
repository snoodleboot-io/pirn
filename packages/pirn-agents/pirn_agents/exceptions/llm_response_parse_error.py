"""``LLMResponseParseError`` — a model's reply could not be parsed as expected."""

from __future__ import annotations


class LLMResponseParseError(ValueError):
    """Raised when a provider reply cannot be parsed into the shape a knot needs.

    An unparseable reply is a real failure of the turn, not an empty result:
    swallowing it hands the caller a plausible-looking blank value (an empty
    mapping, all-``None`` fields) that is indistinguishable from a model that
    genuinely found nothing. Callers that want to retry catch this and drive
    another attempt; callers that do not let it surface as the knot's ``Err``.

    Attributes:
        reply: The raw text that failed to parse, truncated for the message
            but kept in full on the instance.
    """

    #: Characters of ``reply`` included in the exception message.
    _excerpt_length: int = 200

    def __init__(self, message: str, reply: str) -> None:
        """Build the error.

        Args:
            message: What the knot expected and did not get.
            reply: The provider text that failed to parse.
        """
        self.reply = reply
        excerpt = reply[: type(self)._excerpt_length]
        suffix = "..." if len(reply) > type(self)._excerpt_length else ""
        super().__init__(f"{message}; reply was: {excerpt}{suffix}")
