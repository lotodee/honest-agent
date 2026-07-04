"""Safely parse the declared `Content-Length` header.

`str.isdigit()` is NOT a safe guard for `int()`: it accepts non-ASCII digit characters
(e.g. "²") that `int()` rejects, and an all-ASCII value longer than CPython's integer
string-conversion limit (4300 digits) makes `int()` itself raise `ValueError`. Handing
an attacker-controlled header straight to `int()` therefore turns a crafted
`Content-Length` into an unhandled 500 that escapes our RFC 9457 error format — on the
zero-auth visitor door especially. This returns the parsed length (or None if absent)
and raises `BadRequestError` on anything malformed, so the caller renders a clean 400.
"""

from fastapi import Request, Response

from app.core.errors import (
    AppError,
    BadRequestError,
    PayloadTooLargeError,
    app_error_response,
)

# A real Content-Length is a non-negative base-10 integer; the largest plausible value
# (well past any body we accept) still fits in far fewer than 20 ASCII digits. Bounding
# the length here keeps int() below its digit limit, so parsing can never raise.
_MAX_CONTENT_LENGTH_DIGITS = 20


def parse_content_length(value: str | None) -> int | None:
    """The declared body length as an int, None if the header is absent.

    Raises `BadRequestError` (→ RFC 9457 400) on a malformed value instead of letting a
    raw `ValueError` fall through to a generic 500.
    """
    if value is None:
        return None
    if (
        not value.isascii()
        or not value.isdigit()
        or len(value) > _MAX_CONTENT_LENGTH_DIGITS
    ):
        raise BadRequestError("malformed content-length header")
    return int(value)


def enforce_content_length_cap(
    request: Request, max_body_bytes: int, limit_message: str
) -> Response | None:
    """Reject an over-cap or malformed declared Content-Length; None to proceed.

    Returns an RFC 9457 problem-details response — 400 for a malformed length, 413 for a
    declared length over `max_body_bytes` — or None when the request may continue. The
    parse-then-cap check lives here, not inlined per gate, so the two body-cap
    middlewares (owner + visitor) cannot diverge or get half-fixed as they did when the
    raw int() bug had to be patched in each separately.
    """
    instance = request.url.path
    try:
        declared = parse_content_length(request.headers.get("content-length"))
    except AppError as exc:
        return app_error_response(exc, instance=instance)
    if declared is not None and declared > max_body_bytes:
        return app_error_response(
            PayloadTooLargeError(limit_message), instance=instance
        )
    return None
