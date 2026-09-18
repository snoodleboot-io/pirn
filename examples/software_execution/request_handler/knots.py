"""Knot factories for the ``examples.software_execution.request_handler`` example."""

from __future__ import annotations

import asyncio
import json
import time

from pirn.core.knot_factory import KnotFactory

from examples.software_execution.request_handler.account import Account
from examples.software_execution.request_handler.api_response import ApiResponse
from examples.software_execution.request_handler.auth_token import AuthToken
from examples.software_execution.request_handler.parsed_request import ParsedRequest
from examples.software_execution.request_handler.user_profile import UserProfile


@KnotFactory.knot
async def parse_request(raw_body: str, headers_json: str) -> ParsedRequest:
    body = json.loads(raw_body)
    headers = json.loads(headers_json)
    return ParsedRequest(path="/api/process", method="POST", headers=headers, body=body)


@KnotFactory.knot
async def authenticate(request: ParsedRequest) -> AuthToken:
    """Verify the Bearer token. Raises on failure — downstream knots skip."""
    token = request.headers.get("Authorization", "")
    if not token.startswith("Bearer "):
        raise PermissionError("401: missing or invalid token")
    await asyncio.sleep(0.005)
    return AuthToken(user_id="u_abc123", scopes=["read", "write"])


@KnotFactory.knot
async def authorise(auth: AuthToken, required_scope: str) -> AuthToken:
    if required_scope not in auth.scopes:
        raise PermissionError(f"403: missing scope '{required_scope}'")
    return auth


@KnotFactory.knot
async def validate_body(request: ParsedRequest, auth: AuthToken) -> dict:
    if "action" not in request.body:
        raise ValueError("422: 'action' field required")
    return request.body


@KnotFactory.knot
async def fetch_user(auth: AuthToken) -> UserProfile:
    await asyncio.sleep(0.01)
    return UserProfile(user_id=auth.user_id, name="Alice Example", email="alice@example.com")


@KnotFactory.knot
async def fetch_account(auth: AuthToken) -> Account:
    await asyncio.sleep(0.008)
    return Account(account_id="acc_xyz", plan="pro", quota_remaining=950)


@KnotFactory.knot
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


@KnotFactory.knot
async def audit_log(request: ParsedRequest, response: ApiResponse) -> None:
    await asyncio.sleep(0.002)
    print(f"  [audit] {request.method} {request.path} → {response.status}")


@KnotFactory.knot
async def send_notification(user: UserProfile, response: ApiResponse) -> None:
    if response.status == 200:
        await asyncio.sleep(0.003)
        print(f"  [notify] confirmation sent to {user.email}")
