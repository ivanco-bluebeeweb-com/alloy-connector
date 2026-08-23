"""Alloy API HTTP client -- HTTP Basic auth (token as username, secret as
password), sandbox/production base URLs, thin wrappers over the REST verbs.

WHY HTTP BASIC, NOT A TOKEN EXCHANGE FIRST -- see app.py module docstring
for the full architectural reasoning. Alloy's `token`+`secret` pair works
directly as HTTP Basic credentials on every request; there is no mandatory
token endpoint to call first (OAuth Client Credentials via POST /oauth/bearer
exists as an alternative but is not required), confirmed 2026-08-23,
CONNECTOR_DISCOVERY.md.

WHY TWO BASE URLS, SANDBOX FIRST-CLASS.

Alloy's own OpenAPI schema (api-evangelist/alloy-com, cross-checked against
developer.alloy.com) declares `https://sandbox.alloy.co/v1` for testing and
`https://api.alloy.co/v1` for production as two DISTINCT hosts (not a query
param or header toggle). Since this is a compliance/KYC product where
accidentally running a real evaluation against production is a serious
mistake (real credit pulls, real AML screening, potential cost to the
user's own downstream data-provider contracts), `connect_alloy` requires the
user to explicitly choose sandbox or production -- default is sandbox.

WHY EVERY TOKEN VALUE IN A DETAIL MESSAGE IS ALWAYS AN ENTITY/APPLICATION
TOKEN, NEVER THE ACCOUNT'S OWN token/secret CREDENTIAL.

Alloy is a compliance product handling PII; secrets are never echoed back
in any error message this client builds.
"""
from __future__ import annotations

import asyncio
import base64

SANDBOX_BASE = "https://sandbox.alloy.co/v1"
PRODUCTION_BASE = "https://api.alloy.co/v1"

ACCOUNT_MISSING = "ALLOY_ACCOUNT_MISSING"
CREDENTIALS_REJECTED = "ALLOY_CREDENTIALS_REJECTED"
NOT_FOUND = "ALLOY_NOT_FOUND"
METHOD_NOT_ALLOWED = "ALLOY_METHOD_NOT_ALLOWED"
VALIDATION_FAILED = "ALLOY_VALIDATION_FAILED"
RESPONSE_UNEXPECTED = "ALLOY_RESPONSE_UNEXPECTED"
UNREACHABLE = "ALLOY_UNREACHABLE"
RATE_LIMITED = "ALLOY_RATE_LIMITED"
BACKEND_5XX = "ALLOY_BACKEND_5XX"
BACKEND_TIMEOUT = "ALLOY_BACKEND_TIMEOUT"

_MESSAGES = {
    ACCOUNT_MISSING: "No Alloy account is connected yet.",
    CREDENTIALS_REJECTED: "Alloy rejected this token/secret pair. Check both values in Alloy Dashboard > API Key Settings and reconnect.",
    NOT_FOUND: "Alloy has no such record, or this endpoint does not exist for this account's plan.",
    METHOD_NOT_ALLOWED: "Alloy does not allow this HTTP method on this endpoint.",
    VALIDATION_FAILED: "Alloy rejected the request -- the posted data failed validation.",
    RESPONSE_UNEXPECTED: "Alloy returned a response the connector could not safely interpret.",
    UNREACHABLE: "Could not reach Alloy.",
    RATE_LIMITED: "Alloy's rate limit was reached. Try again shortly.",
    BACKEND_5XX: "Alloy returned a server error while processing the request; try again shortly.",
    BACKEND_TIMEOUT: "Alloy took too long to respond; try again shortly.",
}
_RETRYABLE = {RATE_LIMITED, BACKEND_5XX, BACKEND_TIMEOUT}


def fail(code: str, detail: str = "") -> dict:
    message = _MESSAGES.get(code, code)
    if detail:
        message = f"{message} ({detail})"
    return {"ok": False, "error_code": code, "error": message, "retryable": code in _RETRYABLE}


def message_for(code: str) -> str:
    return _MESSAGES.get(code, code)


class ClientFail(Exception):
    def __init__(self, payload: dict):
        super().__init__(payload.get("error", "Alloy request failed"))
        self.payload = payload


def base_url(environment: str) -> str:
    return PRODUCTION_BASE if (environment or "sandbox").lower() == "production" else SANDBOX_BASE


def _headers(token: str, secret: str) -> dict:
    raw = f"{token}:{secret}".encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _check_status(resp, action: str):
    if resp.status_code in (200, 201, 202, 204):
        if resp.status_code == 204:
            return {}
        return resp.body if isinstance(resp.body, (dict, list)) else {}
    if resp.status_code in (401, 403):
        raise ClientFail(fail(CREDENTIALS_REJECTED, action))
    if resp.status_code == 404:
        raise ClientFail(fail(NOT_FOUND, action))
    if resp.status_code == 405:
        raise ClientFail(fail(METHOD_NOT_ALLOWED, action))
    if resp.status_code in (400, 422):
        detail = ""
        if isinstance(resp.body, dict):
            detail = str(resp.body.get("message") or resp.body.get("error") or resp.body.get("errors") or "")
        raise ClientFail(fail(VALIDATION_FAILED, detail or action))
    if resp.status_code == 429:
        raise ClientFail(fail(RATE_LIMITED, action))
    if resp.status_code >= 500:
        raise ClientFail(fail(BACKEND_5XX, action))
    raise ClientFail(fail(RESPONSE_UNEXPECTED, f"{action}: HTTP {resp.status_code}"))


async def check_connection(ctx, token: str, secret: str, environment: str) -> dict:
    """Cheap probe: list entities with a tiny page size, to prove the
    token/secret pair actually works against the chosen environment."""
    resp = await ctx.http.get(
        f"{base_url(environment)}/entities/persons",
        headers=_headers(token, secret),
        params={"page_size": 1},
    )
    try:
        _check_status(resp, "verify connection")
    except ClientFail as e:
        return e.payload
    return {"ok": True}


async def _request(ctx, method: str, token: str, secret: str, environment: str, path: str, *,
                    params: dict | None = None, json: dict | None = None, action: str = "",
                    _retried: bool = False):
    url = f"{base_url(environment)}{path}"
    headers = _headers(token, secret)
    fn = getattr(ctx.http, method)
    kwargs: dict = {"headers": headers}
    if params is not None:
        kwargs["params"] = {k: v for k, v in params.items() if v is not None}
    if json is not None:
        kwargs["json"] = json
    resp = await fn(url, **kwargs)
    if resp.status_code == 429 and not _retried:
        await asyncio.sleep(2.0)
        return await _request(ctx, method, token, secret, environment, path,
                               params=params, json=json, action=action, _retried=True)
    return _check_status(resp, action or path)


async def alloy_get(ctx, token: str, secret: str, environment: str, path: str, *, params: dict | None = None, action: str = ""):
    return await _request(ctx, "get", token, secret, environment, path, params=params, action=action)


async def alloy_post(ctx, token: str, secret: str, environment: str, path: str, *, json: dict | None = None, action: str = ""):
    return await _request(ctx, "post", token, secret, environment, path, json=json, action=action)


async def alloy_put(ctx, token: str, secret: str, environment: str, path: str, *, json: dict | None = None, action: str = ""):
    return await _request(ctx, "put", token, secret, environment, path, json=json, action=action)


async def alloy_delete(ctx, token: str, secret: str, environment: str, path: str, *, params: dict | None = None, action: str = ""):
    return await _request(ctx, "delete", token, secret, environment, path, params=params, action=action)
