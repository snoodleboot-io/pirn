"""Triggers — what starts a run.

A ``Trigger`` connects an external event source (Kafka topic, ValKey
pubsub channel, HTTP webhook, cron schedule) to a tapestry: when an
event arrives, the trigger constructs a ``RunRequest`` and calls
``tapestry.run(request)``.

Triggers are async-iterator-like: they yield ``RunRequest``s as events
arrive, and the runtime calls ``tapestry.run`` for each.  The
``run_forever`` helper drives that loop.
"""
