"""Example: HTTP request processing pipeline with auth, validation, and side effects.

Models a web API handler decomposed as a tapestry:
  parse_request → authenticate → authorise → validate_body
               → fetch_user + fetch_account (parallel)
               → process → audit_log + send_notification (parallel side effects)

Demonstrates:
- Parameterised runs (one tapestry, many requests)
- Parallel fan-out (fetch_user and fetch_account run concurrently)
- Error propagation: downstream knots receive None on auth failure and skip gracefully

Run with:
    uv run python -m examples.software_execution.request_handler
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry

from examples.software_execution.request_handler.knots import (
    audit_log,
    authenticate,
    authorise,
    fetch_account,
    fetch_user,
    parse_request,
    process,
    send_notification,
    validate_body,
)


class RequestHandler:
    """Builds and runs the API handler tapestry for one authorised and one rejected request."""

    _required_scope: ClassVar[str] = "write"
    _token_placeholder: ClassVar[str] = "<set DEMO_TOKEN>"

    @staticmethod
    def build_tapestry() -> Tapestry:
        """Wire parse → auth → authorise → validate/fetch → process → side effects."""
        with Tapestry() as t:
            raw_body = Parameter("raw_body", str, _config=KnotConfig(id="raw_body"))
            hdrs = Parameter("headers_json", str, _config=KnotConfig(id="headers_json"))
            scope = Parameter("required_scope", str, _config=KnotConfig(id="scope"))

            req = parse_request(
                raw_body=raw_body, headers_json=hdrs, _config=KnotConfig(id="parse")
            )
            auth = authenticate(request=req, _config=KnotConfig(id="auth"))
            authz = authorise(auth=auth, required_scope=scope, _config=KnotConfig(id="authz"))
            body = validate_body(request=req, auth=authz, _config=KnotConfig(id="validate"))
            user = fetch_user(auth=authz, _config=KnotConfig(id="fetch_user"))
            acct = fetch_account(auth=authz, _config=KnotConfig(id="fetch_account"))
            resp = process(body=body, user=user, account=acct, _config=KnotConfig(id="process"))
            audit_log(request=req, response=resp, _config=KnotConfig(id="audit"))
            send_notification(user=user, response=resp, _config=KnotConfig(id="notify"))
        return t

    @staticmethod
    def _print_lineage(result: RunResult) -> None:
        """Print one line per knot with an outcome icon."""
        for rec in result.lineage:
            icon = "✓" if rec.outcome == "ok" else ("-" if rec.outcome == "skipped" else "✗")
            print(f"  {icon} {rec.knot_id:<20} {rec.outcome}")

    @classmethod
    async def main(cls) -> None:
        """Handle one authorised request and one unauthenticated request."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))

        t = cls.build_tapestry()

        print("=== Successful request ===")
        demo_token = os.environ.get("DEMO_TOKEN", cls._token_placeholder)
        result = await t.run(
            RunRequest(
                parameters={
                    "raw_body": json.dumps({"action": "summarise", "text": "Hello"}),
                    "headers_json": json.dumps({"Authorization": f"Bearer {demo_token}"}),
                    "required_scope": cls._required_scope,
                }
            )
        )
        await history.record_run(result)
        cls._print_lineage(result)

        print("\n=== Auth failure (no token) ===")
        result2 = await t.run(
            RunRequest(
                parameters={
                    "raw_body": json.dumps({"action": "summarise"}),
                    "headers_json": json.dumps({}),
                    "required_scope": cls._required_scope,
                }
            )
        )
        await history.record_run(result2)
        cls._print_lineage(result2)
