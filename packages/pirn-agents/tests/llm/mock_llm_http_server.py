"""A loopback HTTP server that answers both LLM wire formats, for cross-process tests.

The two-interpreter replay test needs real providers making real HTTP requests,
because an injected client makes a provider identity-keyed by design. This server
stands in for every vendor on ``127.0.0.1``: it answers ``…/chat/completions`` in the
chat-completions shape and ``…/messages`` in the Messages API shape, echoing the
requested model, and records each request path so a test can tell a replay that was
served from the recording apart from one that called the model again.
"""

from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer

from tests.llm.mock_llm_request_handler import MockLLMRequestHandler


class MockLLMHttpServer(ThreadingHTTPServer):
    """Serve canned completions on an ephemeral loopback port in a daemon thread."""

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), MockLLMRequestHandler)
        self.received: list[str] = []
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        """Return the ``http://host:port`` origin the server listens on."""
        host, port = self.server_address[:2]
        return f"http://{host!s}:{port}"

    def record(self, path: str) -> None:
        """Append a request ``path``; called from handler threads."""
        with self._lock:
            self.received.append(path)

    def start(self) -> None:
        """Begin serving in the background."""
        self._thread.start()

    def stop(self) -> None:
        """Stop serving and release the socket."""
        self.shutdown()
        self.server_close()
        self._thread.join(timeout=5)
