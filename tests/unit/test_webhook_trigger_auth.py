"""Tests for WebhookTrigger authentication and rate limiting (H-3 fix)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from starlette.testclient import TestClient

from pirn.triggers.http import WebhookTrigger

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client(trigger: WebhookTrigger) -> TestClient:
    return TestClient(trigger.app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Bearer token authentication
# ---------------------------------------------------------------------------


class TestBearerTokenAuth:
    TOKEN = "test-secret-token"

    def test_missing_auth_header_returns_401(self):
        trigger = WebhookTrigger(path="/run", auth_token=self.TOKEN)
        client = _client(trigger)
        resp = client.post("/run", json={})
        assert resp.status_code == 401
        assert resp.json() == {"error": "unauthorized"}

    def test_wrong_token_returns_401(self):
        trigger = WebhookTrigger(path="/run", auth_token=self.TOKEN)
        client = _client(trigger)
        resp = client.post("/run", json={}, headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 401
        assert resp.json() == {"error": "unauthorized"}

    def test_correct_token_returns_200_with_run_id(self):
        trigger = WebhookTrigger(path="/run", auth_token=self.TOKEN)
        client = _client(trigger)
        resp = client.post(
            "/run",
            json={"key": "value"},
            headers={"Authorization": f"Bearer {self.TOKEN}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["queued"] is True
        assert "run_id" in body

    def test_no_auth_token_set_allows_all_requests(self):
        trigger = WebhookTrigger(path="/run")
        client = _client(trigger)
        resp = client.post("/run", json={})
        assert resp.status_code == 200
        assert resp.json()["queued"] is True

    def test_non_bearer_scheme_returns_401(self):
        trigger = WebhookTrigger(path="/run", auth_token=self.TOKEN)
        client = _client(trigger)
        resp = client.post("/run", json={}, headers={"Authorization": f"Token {self.TOKEN}"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    def test_requests_within_limit_succeed(self):
        trigger = WebhookTrigger(path="/run", rate_limit_rpm=3)
        client = _client(trigger)
        for _ in range(3):
            resp = client.post("/run", json={})
            assert resp.status_code == 200

    def test_request_exceeding_limit_returns_429(self):
        trigger = WebhookTrigger(path="/run", rate_limit_rpm=3)
        client = _client(trigger)
        for _ in range(3):
            client.post("/run", json={})
        resp = client.post("/run", json={})
        assert resp.status_code == 429
        assert resp.json() == {"error": "rate limit exceeded"}

    def test_window_resets_after_60_seconds(self):
        trigger = WebhookTrigger(path="/run", rate_limit_rpm=2)
        client = _client(trigger)

        # Use a controllable clock: pin to t=0 for the first two requests,
        # then advance to t=61 so the old entries are pruned.
        mock_time = MagicMock(return_value=0.0)
        with patch("pirn.triggers.http.time.monotonic", mock_time):
            client.post("/run", json={})
            client.post("/run", json={})
            mock_time.return_value = 61.0
            # At t=61 the old entries are pruned; this should succeed.
            resp = client.post("/run", json={})

        assert resp.status_code == 200
