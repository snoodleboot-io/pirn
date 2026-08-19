"""Triggers — what starts a run.

A ``Trigger`` connects an external event source (Kafka topic, ValKey
pubsub channel, HTTP webhook, cron schedule) to a tapestry: when an
event arrives, the trigger constructs a ``RunRequest`` and calls
``tapestry.run(request)``.

Triggers are async-iterator-like: they yield ``RunRequest``s as events
arrive, and the runtime calls ``tapestry.run`` for each.  The
``run_forever`` helper drives that loop.

Concrete triggers and the driver, each imported from the module that
owns it:

* ``pirn.triggers.base.Trigger`` — base class; implement ``name``,
  ``stream()`` and ``close()``.
* ``pirn.triggers.base.run_forever`` — the driver loop.
* ``pirn.triggers.cron.CronTrigger`` — interval, at-times, or
  caller-supplied schedule.
* ``pirn.triggers.http.WebhookTrigger`` — Starlette ASGI app; one
  ``RunRequest`` per POST.
* ``pirn.triggers.kafka.KafkaTrigger`` — one ``RunRequest`` per message.
* ``pirn.triggers.valkey.ValKeyTrigger`` — one ``RunRequest`` per
  pub-sub message.

No public-API re-exports live here.  The house convention forbids import
forwarding (``.claude/conventions/languages/python.md``), enforced
workspace-wide by ``scripts/check_no_import_forwarding.py``; import each
symbol from the concrete module listed above.
"""
