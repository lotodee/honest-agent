"""The one typed configuration object. Import `get_settings`; never read os.environ."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The backend reads ONE unambiguous env file: backend/.env (server-only secrets),
# anchored to the backend directory so the cwd cannot change which file is read and
# the repo-root .env is never loaded. No frontend build can ever share this file.
_BACKEND_ENV = Path(__file__).resolve().parents[3] / ".env"

# The chunk embedding dimensionality. Deliberately a FIXED module constant, NOT a
# Settings field: it is coupled 1:1 to the chunks.embedding vector(N) column, so it
# must never be a runtime env flip. gemini-embedding-001 returns 3072 natively; the
# embed call (wired Day 4) requests output_dimensionality=768 and L2-normalizes to
# fit vector(768). Changing this is a coordinated code + migration + re-embed change,
# and a schema-match test asserts it equals the migration's vector(N) (ADR-0007).
EMBEDDING_DIM = 768


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # backend/.env only. The real environment (host env / deploy secrets) still
        # wins over the file, so production does not rely on a committed file.
        env_file=_BACKEND_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # Relational + auth (Supabase/Postgres, RLS forced). Required: the service
    # cannot answer for a tenant without its database, so a missing value must
    # fail loudly at startup rather than surface as a runtime error later.
    #
    # database_url is the OWNER connection, used ONLY to apply migrations (create
    # roles/tables). The running app never holds it for tenant data.
    database_url: str

    # app_database_url is the UNPRIVILEGED app_user connection the running service
    # holds (non-owner, non-superuser, no BYPASSRLS). All tenant data goes through
    # this pool via tenant_txn, so the app structurally cannot bypass RLS.
    app_database_url: str

    # Vector store (Weaviate, multi-tenancy on, hybrid search). Required for the
    # same reason as the database.
    weaviate_url: str

    # Gemini via Vertex AI is the only live model. These names are code-defaulted but
    # ENV-OVERRIDABLE (a field is overridden by its uppercase env var automatically),
    # so switching a model is just setting GENERATION_MODEL / EMBEDDING_MODEL. Defaults
    # are the Vertex pre-flight's verified ids (ADR-0007): the intended "gemini-3-flash"
    # does not exist, so gemini-3.5-flash (served at location "global") is the real
    # current flash. generation_model is the ONE place a generation/vision model name
    # lives; never hardcode a model string anywhere else.
    generation_model: str = "google-cloud:gemini-3.5-flash"  # env: GENERATION_MODEL
    embedding_model: str = "gemini-embedding-001"  # env: EMBEDDING_MODEL

    # The Vertex service-account credential. google_credentials_b64 is the deploy
    # path: the SA JSON delivered as base64 in the env, because a free-tier container
    # cannot mount a key file. It is decoded server-side at call time (Day 5), is a
    # crown jewel, and never reaches a browser. gcp_project and gcp_location configure
    # the Vertex client. vertex_credentials_path is the alternative local file path.
    google_credentials_b64: str | None = None
    gcp_project: str | None = None
    # "global" serves the Gemini-3 family (gemini-3.5-flash) AND embeddings; the
    # regional fallback (documented only, ADR-0007) is us-central1 + gemini-2.5-flash.
    gcp_location: str = "global"  # env: GCP_LOCATION
    vertex_credentials_path: str | None = None

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
    # An unknown `kid` (read from the unverified token header) triggers a JWKS
    # refetch. This bounds those refetches to at most one per this many seconds, so an
    # anonymous flood of random-kid tokens cannot amplify into one outbound fetch per
    # request against Supabase's JWKS endpoint. A rotated key is picked up on the first
    # miss after the cooldown.
    owner_jwks_refresh_cooldown_seconds: float = 300.0

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
# google_credentials_b64 IS the Vertex service-account JSON (base64), a crown jewel,
# so it is guarded. vertex_credentials_path is the path to the same JSON; the path is
# guarded too so the location of the crown jewel cannot leak to a browser or a log.
SECRET_SETTINGS_FIELDS = frozenset(
    {
        "supabase_service_role_key",
        "mcp_signing_secret",
        "google_credentials_b64",
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
