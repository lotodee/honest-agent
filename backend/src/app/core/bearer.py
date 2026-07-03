"""Parse an `Authorization: Bearer` header. Shared by the owner and MCP doors."""

from app.core.errors import AuthenticationError


def parse_bearer(header: str | None) -> str:
    if header is None:
        raise AuthenticationError("missing authorization header")
    scheme, _, value = header.partition(" ")
    token = value.strip()
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("malformed authorization header")
    return token
