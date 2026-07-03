"""The secret-on-server guard: service/model secrets never reach a browser bundle."""

import json

from fastapi import FastAPI

from app.core.settings import SECRET_SETTINGS_FIELDS, Settings, secret_values


def test_secret_registry_names_the_crown_jewels() -> None:
    # Every server-only secret Settings can hold: Supabase service_role, the MCP
    # signing secret, and the path to the Vertex service-account JSON.
    assert {
        "supabase_service_role_key",
        "mcp_signing_secret",
        "vertex_credentials_path",
    } <= SECRET_SETTINGS_FIELDS


def test_no_secret_field_name_surfaces_in_a_response_model(app: FastAPI) -> None:
    # Every response model the browser can see is in the OpenAPI components. If a
    # secret-bearing field name ever appears as a response property, this fails.
    components = app.openapi().get("components", {}).get("schemas", {})
    response_fields = {
        field
        for schema in components.values()
        for field in schema.get("properties", {})
    }
    assert SECRET_SETTINGS_FIELDS.isdisjoint(response_fields)


def test_no_secret_value_appears_in_browser_facing_openapi(
    app: FastAPI, settings: Settings
) -> None:
    rendered = json.dumps(app.openapi())
    for secret in secret_values(settings):
        assert secret not in rendered


def test_secret_values_excludes_public_identifiers(settings: Settings) -> None:
    # The public widget key and anon key are identifiers, not secrets; they must
    # not be treated as crown jewels by the guard.
    assert "widget_public_key" not in SECRET_SETTINGS_FIELDS
    assert "supabase_anon_key" not in SECRET_SETTINGS_FIELDS
