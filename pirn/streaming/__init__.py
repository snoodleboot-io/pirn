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
