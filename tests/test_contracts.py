"""Offline contract tests for Alloy Connector.

These tests never call Alloy or require credentials. They ensure handler
parameter use, manifest registration, and per-function pricing cannot drift
apart as the connector grows.
"""
from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

from pydantic import BaseModel

import main  # noqa: F401 - imports every handler/panel for registration
from app import chat

ROOT = Path(__file__).resolve().parents[1]
VALID_PRICES = {0, 8, 16, 20, 40, 60}


def _param_attributes(func) -> set[str]:
    """Return attributes accessed as ``params.some_field`` in a handler."""
    tree = ast.parse(inspect.getsource(func))
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "params"
    }


def test_every_handler_uses_a_pydantic_param_model() -> None:
    assert len(chat._functions) == 70
    for name, definition in chat._functions.items():
        assert isinstance(definition._pydantic_model, type), name
        assert issubclass(definition._pydantic_model, BaseModel), name


def test_handlers_only_read_declared_param_fields() -> None:
    for name, definition in chat._functions.items():
        declared = set(definition._pydantic_model.model_fields)
        accessed = _param_attributes(definition.func)
        assert accessed <= declared, (
            f"{name} uses undeclared fields {sorted(accessed - declared)}; "
            f"schema fields are {sorted(declared)}"
        )


def test_manifest_exactly_matches_registered_functions() -> None:
    manifest = json.loads((ROOT / "imperal.json").read_text())
    manifest_tools = {tool["name"] for tool in manifest["tools"]}
    assert manifest_tools == set(chat._functions)


def test_every_manifest_function_has_a_valid_price() -> None:
    manifest = json.loads((ROOT / "imperal.json").read_text())
    prices = json.loads((ROOT / "tool-prices.json").read_text())
    manifest_tools = {tool["name"] for tool in manifest["tools"]}
    assert set(prices) == manifest_tools
    assert set(prices.values()) <= VALID_PRICES
