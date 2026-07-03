"""The one typed configuration object. Import `get_settings`; never read os.environ."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # The .env lives at the repo root while the backend runs from backend/, so
        # look in both: "../.env" resolves it when run from backend/, ".env" when
        # run from the repo root. The real environment always wins over either.
        env_file=(".env", "../.env"),
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

    # Owner door: verifying a real Supabase login JWT. issuer and jwks_url are
    # environment-specific, so they are required and have no default; a missing
    # value must fail loudly rather than silently accept tokens from the wrong
    # issuer. The audience defaults to Supabase's standard "authenticated".
    supabase_jwt_issuer: str
    supabase_jwks_url: str
    supabase_jwt_audience: str = "authenticated"

    # MCP door: the self-minted external-caller token. The signing secret is a
    # crown jewel (server-side only) and is required. The issuer and audience are
    # our own literals: audience is THIS server, so a token minted for anything
    # else is rejected. These are a different credential domain from the Supabase
    # JWT above on purpose.
    mcp_signing_secret: str
    # These two are public protocol identifiers, not secrets; S105 only fires on
    # the word "token" in the field name.
    mcp_token_issuer: str = "honest-agent"  # noqa: S105
    mcp_token_audience: str = "honest-agent-mcp"  # noqa: S105
    mcp_allowed_origins: tuple[str, ...] = ()
    # The Host-header values this server actually serves under. The DNS-rebinding
    # defence: a rebound, attacker-chosen Host is rejected. Defaults to the local
    # loopback names; set to the real domain on deploy (Day 9).
    mcp_allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")

    # Visitor door: reject an over-large body before parsing it, so an anonymous
    # visitor cannot exhaust memory even while the rate limiter is stubbed.
    visitor_max_body_bytes: int = 65536

    # Observability. Both stay inert while unset.
    logfire_token: str | None = None
    sentry_dsn: str | None = None

    # The only secret the widget bundle is allowed to carry.
    widget_public_key: str | None = None


# The settings fields that carry a server-only secret value. The secret-on-server
# guard and the non-leak tests enumerate these; nothing here may reach a browser
# bundle, a log line, or an error body. The public widget key and anon key are
# deliberately NOT here: they are public identifiers.
#
# vertex_credentials_path is the path to the Vertex service-account JSON (the crown
# jewel). The JSON CONTENT is never loaded into Settings, only read server-side at
# call time, so the path is the only Vertex value Settings holds; it is guarded too
# so the location of the crown jewel cannot leak to a browser or a log.
SECRET_SETTINGS_FIELDS = frozenset(
    {
        "supabase_service_role_key",
        "mcp_signing_secret",
        "vertex_credentials_path",
    }
)


def secret_values(settings: Settings) -> frozenset[str]:
    """The concrete secret strings currently configured, for non-leak assertions."""
    values = {getattr(settings, name) for name in SECRET_SETTINGS_FIELDS}
    return frozenset(value for value in values if isinstance(value, str) and value)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
