"""Exact-host Origin/Referer matching, shared by the visitor gate and the MCP door.

A naive substring or startswith check lets `allowed.com.evil.com` and
`evil-allowed.com` through, so this compares the full host exactly against a
lowercased allowlist.
"""

from urllib.parse import urlsplit


def origin_host(value: str) -> str | None:
    """The lowercased host of an Origin/Referer value, or None if it has none.

    Empty, `null`, and any value without both a scheme and a host return None so
    they can never match an allowlist. A trailing dot is stripped so `allowed.com.`
    cannot dodge an `allowed.com` entry.
    """
    candidate = value.strip()
    if not candidate or candidate.lower() == "null":
        return None
    parts = urlsplit(candidate)
    if not parts.scheme or not parts.hostname:
        return None
    return parts.hostname.rstrip(".")


def host_allowed(value: str, allowed_hosts: frozenset[str]) -> bool:
    host = origin_host(value)
    return host is not None and host in allowed_hosts
