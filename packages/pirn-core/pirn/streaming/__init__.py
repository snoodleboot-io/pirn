"""Streaming sources — continuous data feeds for long-running runs.

A ``StreamingSource`` is a knot that yields a sequence of values over
its lifetime, rather than producing a single result.  Downstream
knots run once per yielded value.

Different from triggers: a *trigger* fires whole runs (each event
becomes a fresh ``RunRequest``).  A *streaming source* feeds continuous
data into a single long-running pipeline.  Use triggers for
request/response patterns; use streaming sources for ETL-style
continuous transformation.

Concrete sources, each imported from the module that owns it:

* ``pirn.streaming.iterable_source.IterableSource`` — wraps any async iterable
  (tests, simple cases).
* ``pirn.streaming.kafka_streaming_source.KafkaStreamingSource`` — streams Kafka messages.
* ``pirn.streaming.file_tail_source.FileTailSource`` — tails a file like ``tail -f``.

Streaming is driven by ``source.run_stream(tapestry)`` (:meth:`pirn.streaming.streaming_source.StreamingSource.run_stream`),
which ticks the tapestry once per yielded value.  There is no
``Tapestry.run_stream`` method — the driver is a free function, so the
engine carries no streaming-specific surface.

No public-API re-exports live here.  The house convention forbids import
forwarding (``.claude/conventions/languages/python.md``), enforced
workspace-wide by ``scripts/check_no_import_forwarding.py``; import each
symbol from the concrete module listed above.
"""
