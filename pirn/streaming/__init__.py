"""Streaming sources — continuous data feeds for long-running runs.

A ``StreamingSource`` is a knot that yields a sequence of values over
its lifetime, rather than producing a single result.  Downstream
knots run once per yielded value.

Different from triggers: a *trigger* fires whole runs (each event
becomes a fresh ``RunRequest``).  A *streaming source* feeds continuous
data into a single long-running pipeline.  Use triggers for
request/response patterns; use streaming sources for ETL-style
continuous transformation.

Concrete sources:

* ``IterableSource`` — wraps any async iterable (tests, simple cases).
* ``KafkaStreamingSource`` — streams Kafka messages.
* ``FileTailSource`` — tails a file like ``tail -f``.

The engine's streaming mode is opt-in via ``Tapestry.run_stream(...)``.
"""

from pirn.streaming.base import StreamingSource, run_stream
from pirn.streaming.iterable import IterableSource

# Optional sources — guarded import; users without the dep get a
# helpful ImportError on first use.
try:
    from pirn.streaming.kafka import KafkaStreamingSource
except ImportError:
    KafkaStreamingSource = None  # type: ignore[assignment]

from pirn.streaming.file_tail import FileTailSource
from pirn.streaming.trigger_adapter import StreamingSourceTrigger

__all__ = [
    "FileTailSource",
    "IterableSource",
    "KafkaStreamingSource",
    "StreamingSource",
    "StreamingSourceTrigger",
    "run_stream",
]
