"""The async database access seam. Reads the URL from settings; no engine yet."""

from dataclasses import dataclass

from app.core.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class DatabaseSessions:
    """Per-request async session provider.

    Carries the connection URL from settings. The concrete async engine
    (asyncpg behind SQLAlchemy) is wired when the first tenant-scoped query
    lands; until then this is the typed injection point every tenant router
    depends on, so the wiring changes in one place.
    """

    database_url: str


def build_db_sessions(settings: Settings) -> DatabaseSessions:
    return DatabaseSessions(database_url=settings.database_url)


async def get_db_sessions() -> DatabaseSessions:
    return build_db_sessions(get_settings())
