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
    uv run python examples/software_execution/request_handler.py
"""

import asyncio
import json
import time
from dataclasses import dataclass

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- models


@dataclass
class ParsedRequest:
    path: str
    method: str
    headers: dict
    body: dict


@dataclass
class AuthToken:
    user_id: str
    scopes: list


@dataclass
class UserProfile:
    user_id: str
    name: str
    email: str


@dataclass
class Account:
    account_id: str
    plan: str
    quota_remaining: int


@dataclass
class ApiResponse:
    status: int
    body: dict
    duration_ms: float


# ----------------------------------------------------------------- knots


@knot
async def parse_request(raw_body: str, headers_json: str) -> ParsedRequest:
    body = json.loads(raw_body)
    headers = json.loads(headers_json)
    return ParsedRequest(path="/api/process", method="POST", headers=headers, body=body)


@knot
async def authenticate(request: ParsedRequest) -> AuthToken:
    """Verify the Bearer token. Raises on failure — downstream knots skip."""
    token = request.headers.get("Authorization", "")
    if not token.startswith("Bearer "):
        raise PermissionError("401: missing or invalid token")
    await asyncio.sleep(0.005)
    return AuthToken(user_id="u_abc123", scopes=["read", "write"])


@knot
async def authorise(auth: AuthToken, required_scope: str) -> AuthToken:
    if required_scope not in auth.scopes:
        raise PermissionError(f"403: missing scope '{required_scope}'")
    return auth


@knot
async def validate_body(request: ParsedRequest, auth: AuthToken) -> dict:
    if "action" not in request.body:
        raise ValueError("422: 'action' field required")
    return request.body


@knot
async def fetch_user(auth: AuthToken) -> UserProfile:
    await asyncio.sleep(0.01)
    return UserProfile(user_id=auth.user_id, name="Alice Example", email="alice@example.com")


@knot
async def fetch_account(auth: AuthToken) -> Account:
    await asyncio.sleep(0.008)
    return Account(account_id="acc_xyz", plan="pro", quota_remaining=950)


@knot
async def process(body: dict, user: UserProfile, account: Account) -> ApiResponse:
    if account.quota_remaining <= 0:
        raise RuntimeError("429: quota exhausted")
    t0 = time.monotonic()
    await asyncio.sleep(0.02)
    return ApiResponse(
        status=200,
        body={"result": "ok", "action": body["action"], "user": user.name},
        duration_ms=(time.monotonic() - t0) * 1000,
    )


@knot
async def audit_log(request: ParsedRequest, response: ApiResponse) -> None:
    await asyncio.sleep(0.002)
    print(f"  [audit] {request.method} {request.path} → {response.status}")


@knot
async def send_notification(user: UserProfile, response: ApiResponse) -> None:
    if response.status == 200:
        await asyncio.sleep(0.003)
        print(f"  [notify] confirmation sent to {user.email}")


# ----------------------------------------------------------------- wiring


def build_tapestry() -> Tapestry:
    with Tapestry() as t:
        raw_body = Parameter("raw_body", str, _config=KnotConfig(id="raw_body"))
        hdrs = Parameter("headers_json", str, _config=KnotConfig(id="headers_json"))
        scope = Parameter("required_scope", str, _config=KnotConfig(id="scope"))

        req = parse_request(raw_body=raw_body, headers_json=hdrs, _config=KnotConfig(id="parse"))
        auth = authenticate(request=req, _config=KnotConfig(id="auth"))
        authz = authorise(auth=auth, required_scope=scope, _config=KnotConfig(id="authz"))
        body = validate_body(request=req, auth=authz, _config=KnotConfig(id="validate"))
        user = fetch_user(auth=authz, _config=KnotConfig(id="fetch_user"))
        acct = fetch_account(auth=authz, _config=KnotConfig(id="fetch_account"))
        resp = process(body=body, user=user, account=acct, _config=KnotConfig(id="process"))
        audit_log(request=req, response=resp, _config=KnotConfig(id="audit"))
        send_notification(user=user, response=resp, _config=KnotConfig(id="notify"))
    return t


# ----------------------------------------------------------------- main


async def main() -> None:
    from pirn.backends.sqlite.sqlite_history import SQLiteHistory
    history = SQLiteHistory()

    t = build_tapestry()

    print("=== Successful request ===")
    result = await t.run(
        RunRequest(
            parameters={
                "raw_body": json.dumps({"action": "summarise", "text": "Hello"}),
                "headers_json": json.dumps({"Authorization": "Bearer valid-token-xyz"}),
                "required_scope": "write",
            }
        )
    )
    await history.record_run(result)
    for rec in result.lineage:
        icon = "✓" if rec.outcome == "ok" else ("-" if rec.outcome == "skipped" else "✗")
        print(f"  {icon} {rec.knot_id:<20} {rec.outcome}")

    print("\n=== Auth failure (no token) ===")
    result2 = await t.run(
        RunRequest(
            parameters={
                "raw_body": json.dumps({"action": "summarise"}),
                "headers_json": json.dumps({}),
                "required_scope": "write",
            }
        )
    )
    await history.record_run(result2)
    for rec in result2.lineage:
        icon = "✓" if rec.outcome == "ok" else ("-" if rec.outcome == "skipped" else "✗")
        print(f"  {icon} {rec.knot_id:<20} {rec.outcome}")


if __name__ == "__main__":
    asyncio.run(main())
