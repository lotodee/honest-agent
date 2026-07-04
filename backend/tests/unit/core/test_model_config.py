"""The Vertex model/location config is the pre-flight decision (ADR-0007): model
names are pinned defaults but env-overridable; the embedding DIMENSION is NOT — it is
a fixed constant coupled to the chunks.embedding vector(N) column and guarded by a
schema-match test. `_env_file=None` tests the CODE defaults, ignoring any local
backend/.env so the assertions hold identically in CI.
"""

import pathlib
import re

import pytest

from app.core.settings import EMBEDDING_DIM, Settings

_CHUNKS_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[4]
    / "supabase"
    / "migrations"
    / "0003_chunks.sql"
)


def test_model_defaults_are_the_preflight_ids() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.generation_model == "google-cloud:gemini-3.5-flash"
    assert settings.embedding_model == "gemini-embedding-001"
    assert settings.gcp_location == "global"


def test_invalid_gemini_3_flash_is_never_the_default() -> None:
    # Regression guard: the pre-flight proved this id 404s in every location.
    assert Settings(_env_file=None).generation_model != "google-cloud:gemini-3-flash"  # type: ignore[call-arg]


def test_model_names_and_location_are_env_overridable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GENERATION_MODEL", "google-cloud:gemini-2.5-flash")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-005")
    monkeypatch.setenv("GCP_LOCATION", "us-central1")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.generation_model == "google-cloud:gemini-2.5-flash"
    assert settings.embedding_model == "text-embedding-005"
    assert settings.gcp_location == "us-central1"


def test_embedding_dim_is_a_constant_not_env_overridable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A module constant, not a Settings field: an env var cannot flip it and silently
    # drift from the chunks.embedding column.
    monkeypatch.setenv("EMBEDDING_DIM", "1536")
    assert EMBEDDING_DIM == 768
    assert not hasattr(Settings(_env_file=None), "embedding_dim")  # type: ignore[call-arg]


def test_embedding_dim_matches_the_chunks_migration() -> None:
    # Fails CI if EMBEDDING_DIM and the chunks.embedding vector(N) column ever drift.
    sql = _CHUNKS_MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"embedding\s+vector\((\d+)\)", sql)
    assert match is not None, "chunks.embedding vector(N) not found in the migration"
    assert int(match.group(1)) == EMBEDDING_DIM
