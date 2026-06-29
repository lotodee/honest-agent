"""The one typed configuration object. Import `get_settings`; never read os.environ."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # Relational + auth (Supabase/Postgres, RLS forced). Required: the service
    # cannot answer for a tenant without its database, so a missing value must
    # fail loudly at startup rather than surface as a runtime error later.
    database_url: str

    # Vector store (Weaviate, multi-tenancy on, hybrid search). Required for the
    # same reason as the database.
    weaviate_url: str

    # Gemini via Vertex AI is the only live model. The service-account JSON is the
    # one credential that can spend money, so it stays server-side and is None
    # until provisioned.
    vertex_credentials_path: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    # Supabase keys. service_role bypasses RLS, so leaking it defeats tenant
    # isolation; it lives only in host env and CI secrets.
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None

    # Observability. Both stay inert while unset.
    logfire_token: str | None = None
    sentry_dsn: str | None = None

    # The only secret the widget bundle is allowed to carry.
    widget_public_key: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
