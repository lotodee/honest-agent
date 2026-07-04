"""The Vertex model/location config is the pre-flight decision (ADR-0007), pinned
and env-overridable. `_env_file=None` tests the CODE defaults, ignoring any local
backend/.env so the assertions hold identically in CI.
"""

import pytest

from app.core.settings import Settings


def test_model_defaults_are_the_preflight_ids() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.generation_model == "google-cloud:gemini-3.5-flash"
    assert settings.embedding_model == "gemini-embedding-001"
    assert settings.gcp_location == "global"
    assert settings.embedding_dim == 768


def test_invalid_gemini_3_flash_is_never_the_default() -> None:
    # Regression guard: the pre-flight proved this id 404s in every location.
    assert Settings(_env_file=None).generation_model != "google-cloud:gemini-3-flash"  # type: ignore[call-arg]


def test_model_config_is_env_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENERATION_MODEL", "google-cloud:gemini-2.5-flash")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-005")
    monkeypatch.setenv("GCP_LOCATION", "us-central1")
    monkeypatch.setenv("EMBEDDING_DIM", "1536")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.generation_model == "google-cloud:gemini-2.5-flash"
    assert settings.embedding_model == "text-embedding-005"
    assert settings.gcp_location == "us-central1"
    assert settings.embedding_dim == 1536
