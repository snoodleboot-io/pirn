"""Record/replay execution — serving a knot's recorded output instead of running it.

Every pirn run already *records*: the engine writes a ``KnotLineage`` row per
knot invocation and puts each ``Ok`` value into the ``DataStore`` keyed by its
content hash.  What core lacked was the other half — a way to *replay* that
recording, resolving a knot's output from the store rather than executing the
knot.  ``pirn.replay`` re-executes the pipeline; this package does not.

See ``pirn.recording.replay_session.ReplaySession`` for the entry point.
"""

from __future__ import annotations
