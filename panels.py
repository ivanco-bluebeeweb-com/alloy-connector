"""Panel UI -- connections list/connect form for Alloy Connector.

SIDEBAR CONTENT -- NO CARDS ANYWHERE, per ~/UI_INTERFACE_STANDARD.md's
"left sidebar, no decorated cards" rule (same convention as Cin7 Core
Connector's / MuleSoft Connector's / Shopify Connector's panels.py).

Every section (connections, connect form) is a plain ui.Stack, content
stacked vertically and left-aligned, sections separated by ui.Divider() --
no Card border/background/shadow anywhere in this slot. Disconnect lives
only in the "App settings" screen (panels_settings.py). The one secondary
"App settings" button is always the LAST element at the bottom of the
sidebar.

FORM CONTRACT (per Vlad's UI_INTERFACE_STANDARD.md instruction,
2026-08-21): every input carries its own visible label (a ui.Text caption
above it, never a bare placeholder standing in for a label), and the
placeholder text itself is contextually specific to what belongs in that
field -- never a generic restatement of the label. The form container is
forced to the sidebar's full width (align="stretch" on every wrapping
Stack) and its own content stretches to fill it in turn. No instructions
duplicated here that already live in alloy_connect_help's modal.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
import handlers as h


def _settings_button() -> ui.UINode:
    """The one required secondary entry point into the settings screen --
    always the last element at the bottom of the sidebar."""
    return ui.Button(
        "App settings", variant="secondary", size="sm", full_width=True,
        icon="settings", on_click=ui.Call("__panel__alloy_settings"),
    )


def _connection_row(c: dict) -> ui.UINode:
    label = c.get("label") or c.get("environment", "")
    return ui.Stack(direction="v", gap=1, children=[
        ui.Text(label, variant="body"),
        ui.Text(f"Environment: {c.get('environment', 'sandbox')}", variant="caption"),
    ])


def _connections_section(connections: list[dict]) -> ui.UINode:
    if not connections:
        return ui.Text("No Alloy accounts connected yet.", variant="caption")
    children: list[ui.UINode] = []
    for i, c in enumerate(connections):
        if i > 0:
            children.append(ui.Divider())
        children.append(_connection_row(c))
    return ui.Stack(direction="v", gap=2, children=children)


def _connect_section() -> ui.UINode:
    """Plain content, no Card wrapper. Stretched full-width per
    UI_INTERFACE_STANDARD.md (2026-08-21). No intro heading/description
    text here -- the setup walkthrough lives ONLY in alloy_connect_help's
    modal (button below opens it); repeating it here would duplicate that
    instruction."""
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Button("How do I set this up?", variant="ghost", size="sm",
                  icon="HelpCircle",
                  on_click=ui.Call("__panel__alloy_connect_help")),
        ui.Form(
            action="connect_alloy",
            submit_label="Verify and connect",
            children=[
                ui.Stack(direction="v", gap=1, align="stretch", children=[
                    ui.Text("Token", variant="caption"),
                    ui.Input(param_name="token",
                             placeholder="Account token from Dashboard > API Key Settings"),
                ]),
                ui.Stack(direction="v", gap=1, align="stretch", children=[
                    ui.Text("Secret", variant="caption"),
                    ui.Password(param_name="secret",
                                placeholder="Account secret from the same API Key Settings page"),
                ]),
                ui.Stack(direction="v", gap=1, align="stretch", children=[
                    ui.Text("Environment", variant="caption"),
                    ui.Select(param_name="environment", default="sandbox", options=[
                        {"label": "Sandbox (testing)", "value": "sandbox"},
                        {"label": "Production (live evaluations)", "value": "production"},
                    ]),
                ]),
                ui.Stack(direction="v", gap=1, align="stretch", children=[
                    ui.Text("Label (optional)", variant="caption"),
                    ui.Input(param_name="label", placeholder="e.g. Underwriting sandbox"),
                ]),
            ],
        ),
    ])


@ext.panel("alloy_connect", slot="left", title="Alloy", icon="🛡️",
           default_width=320, min_width=260, max_width=420)
async def alloy_connect_panel(ctx, **kwargs) -> object:
    connections = await h._load_connections(ctx)
    connected = bool(connections)

    header = ui.Header(text="Alloy", level=2,
                        subtitle="Run KYC/KYB/AML/fraud/credit decisioning from Imperal")

    if not connected:
        return ui.Stack(direction="v", gap=4, align="stretch", children=[
            header,
            _connect_section(),
            ui.Divider(),
            _settings_button(),
        ])

    return ui.Stack(direction="v", gap=4, align="stretch", children=[
        header,
        ui.Text("Connected accounts", variant="subtitle"),
        _connections_section(connections),
        ui.Divider(),
        _connect_section(),
        ui.Divider(),
        _settings_button(),
    ])


@ext.panel("alloy_connect_help", slot="center",
           title="How to connect Alloy", center_overlay=True)
async def alloy_connect_help(ctx, **kwargs) -> object:
    content = ui.Stack(direction="v", gap=3, children=[
        ui.Alert(
            title="Alloy.com, not Alloy Automation",
            message=(
                "This connects Alloy.com's identity decisioning platform "
                "(developer.alloy.com) -- KYC/KYB/AML/fraud/credit for "
                "banks and fintechs. Alloy Automation (runalloy.com) is a "
                "different product (embedded iPaaS for e-commerce) and is "
                "not supported here."
            ),
            type="warning",
        ),
        ui.Divider(),
        ui.Text("1. Sign in to your Alloy Dashboard."),
        ui.Text("2. Open API Key Settings."),
        ui.Text("3. Choose the environment (Sandbox or Production) you want to connect."),
        ui.Text("4. Copy the token and secret shown for that environment."),
        ui.Text("5. Paste both into the form and pick the matching environment -- Alloy checks them immediately on connect."),
        ui.Divider(),
        ui.Link(
            label="Open Alloy's official API documentation",
            href="https://developer.alloy.com/",
        ),
    ])
    return ui.Dialog(
        title="How to connect Alloy",
        content=content,
        confirm_label="",
        cancel_label="Close",
    )


@ext.panel("alloy_center", slot="center", title="Alloy", icon="🛡️", center_overlay=True)
async def alloy_center_panel(ctx, **kwargs) -> object:
    """Base center panel -- per UI_INTERFACE_STANDARD.md (2026-08-20).
    This app has no list/detail content of its own to show in the center
    by default (everything lives in the sidebar). MUST carry
    center_overlay=True: per docs.imperal.io/en/concepts/panels, a plain
    slot="center" panel is registered but the Panel app never fetches it
    at session-init without that flag. Text is the shared canonical
    wording -- must stay identical across every app in this situation."""
    return ui.Empty(
        message="Nothing to show here -- this app is managed entirely from the sidebar.",
        icon="👈",
    )
