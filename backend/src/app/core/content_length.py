"""Safely parse the declared `Content-Length` header.

`str.isdigit()` is NOT a safe guard for `int()`: it accepts non-ASCII digit characters
(e.g. "²") that `int()` rejects, and an all-ASCII value longer than CPython's integer
string-conversion limit (4300 digits) makes `int()` itself raise `ValueError`. Handing
an attacker-controlled header straight to `int()` therefore turns a crafted
`Content-Length` into an unhandled 500 that escapes our RFC 9457 error format — on the
zero-auth visitor door especially. This returns the parsed length (or None if absent)
and raises `BadRequestError` on anything malformed, so the caller renders a clean 400.
"""

from app.core.errors import BadRequestError

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
