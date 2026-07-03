"""The rate-limit seam. The interface is real; the implementation is a Day-11 stub."""

from typing import Protocol


class RateLimiter(Protocol):
    async def check(self, *, widget_key: str, client_ip: str | None) -> bool:
        """Return True to allow the request, False to reject it (429)."""
        ...


class AllowAllRateLimiter:
    """Day-1 stub: always allows. Swapped for a real limiter on Day 11, not added."""

    async def check(self, *, widget_key: str, client_ip: str | None) -> bool:
        return True
