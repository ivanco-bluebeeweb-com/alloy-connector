"""Extension declaration, secrets, lifecycle hooks.

WHY BYOK (bring-your-own-key), same reasoning as Cin7 Core Connector /
MuleSoft Connector / Shopify Connector. The user's Alloy account is THEIR
OWN identity-decisioning account (their own bank/fintech's Alloy tenant)
-- Imperal cannot and should not broker access to someone else's Alloy
organization centrally, and this data is highly sensitive (PII/KYC/AML).

WHY HTTP BASIC (token+secret) AS THE PRIMARY AUTH PATH, NOT OAUTH.

Alloy's API (developer.alloy.com, confirmed during Discovery 2026-08-23,
CONNECTOR_DISCOVERY.md) supports BOTH HTTP Basic auth (token as username,
secret as password) and OAuth 2.0 Client Credentials (POST /oauth/bearer)
on the SAME token+secret pair issued once in the Alloy Dashboard's API Key
Settings page. HTTP Basic needs no extra network round trip and no token
refresh bookkeeping, so it is the primary path here -- the same
"paste your own ready-made credentials" shape already used by Cin7 Core
Connector (Account ID + Application Key) and MuleSoft Connector (Connected
App client id/secret).

WHY write_mode="both", SAME REASONING AS EVERY OTHER BYOK CONNECTOR IN THE
PORTFOLIO (Shopify/Cin7 Core/MuleSoft/n8n/Power Automate).

Declaring write_mode="user" would mean only the platform's generic Secrets
screen could write these -- leaving a first-time user with no in-app screen
explaining what a token/secret even are or where to find them. "both" keeps
the generic Secrets screen as a fallback while letting `connect_alloy` be
the friendly guided path.

WHY SCOPE IS PER-ACCOUNT, NOT APP-LEVEL, SAME AS EVERY OTHER BYOK
CONNECTOR IN THE PORTFOLIO.

Different Imperal users must never see each other's Alloy connections --
this is identity-decisioning data governed by KYC/AML compliance
obligations. Secrets are stored per-account, and a user may connect
MULTIPLE Alloy accounts/environments (e.g. one sandbox + one production,
or an agency managing several clients' Alloy tenants) -- `alloy_connections`
holds a JSON array, matching the multi-connection shape of every other
BYOK connector in the portfolio.

NAME TRAP GUARDED EXPLICITLY (see CONNECTOR_DISCOVERY.md Critical #1):
Alloy Automation (runalloy.com, embedded iPaaS) and Alloy.com (identity
decisioning) are two DIFFERENT products with different APIs and different
credentials. This extension is Alloy.com identity decisioning ONLY --
every user-facing string says so explicitly to avoid a user pasting the
wrong product's credentials here by mistake.
"""
from __future__ import annotations

from imperal_sdk import ChatExtension, Extension

ext = Extension(
    "alloy-connector",
    version="0.1.0",
    display_name="Alloy",
    description=(
        "Connect your own Alloy.com identity decisioning account via its "
        "API token + secret. Run KYC/KYB/AML/fraud/credit evaluations, "
        "manage person and business entities, launch and review Journey "
        "applications (with manual-review approvals), upload identity "
        "documents, monitor customers continuously via the Events API, "
        "run cases and investigations, manage custom watchlists, published "
        "attributes, bank accounts/transactions, and webhooks -- through "
        "Alloy's identity decisioning API. Not compatible with Alloy "
        "Automation, a different product (embedded iPaaS for e-commerce)."
    ),
    icon="icon.svg",
    capabilities=[
        "alloy:read",
        "alloy:write",
    ],
    actions_explicit=True,
    system=False,
)

chat = ChatExtension(
    ext,
    tool_name="alloy",
    description=(
        "Alloy Connector -- connect your own Alloy.com identity decisioning "
        "account via API token + secret, then run KYC/KYB/AML/fraud/credit "
        "evaluations, manage entities, journeys/applications, documents, "
        "events monitoring, cases/investigations, custom lists, published "
        "attributes, bank accounts/transactions, reviews, and webhooks."
    ),
)

ext.secret(
    "alloy_connections",
    (
        "Your connected Alloy accounts -- stored as a JSON array, one "
        "entry per account/environment, each with its API token and "
        "secret. Managed through connect_alloy / disconnect_alloy -- you "
        "should not need to edit this directly."
    ),
    required=True,
    write_mode="both",
    max_bytes=65536,
    rotation_hint_days=180,
)(lambda: None)


@ext.health_check
async def health_check(ctx) -> dict:
    """Fast configuration health; no third-party call -- just confirms at
    least one account connection is stored, same shape as Cin7 Core's/
    Shopify's health_check."""
    import json as _json
    raw = await ctx.secrets.get("alloy_connections")
    try:
        count = len(_json.loads(raw)) if raw else 0
    except Exception:
        count = 0
    return {
        "healthy": True,
        "detail": (
            f"{count} Alloy account(s) connected." if count
            else "Not connected yet -- run connect_alloy."
        ),
    }
