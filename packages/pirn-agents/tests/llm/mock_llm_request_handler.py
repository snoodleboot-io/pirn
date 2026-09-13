"""Request handler for :class:`tests.llm.mock_llm_http_server.MockLLMHttpServer`."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any


class MockLLMRequestHandler(BaseHTTPRequestHandler):
    """Answer a completion POST in the wire format its path names."""

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        model = str(request.get("model", ""))
        # Imported here: the server module imports this handler at load time.
        from tests.llm.mock_llm_http_server import MockLLMHttpServer

        if isinstance(self.server, MockLLMHttpServer):
            self.server.record(self.path)
        body = self._messages_reply(model) if "/messages" in self.path else self._chat_reply(model)
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        """Keep test output quiet."""
        return None

    @staticmethod
    def _chat_reply(model: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": f"reply from {model}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 3},
        }

    @staticmethod
    def _messages_reply(model: str) -> dict[str, Any]:
        return {
            "content": [{"type": "text", "text": f"reply from {model}"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 3, "output_tokens": 3},
        }
