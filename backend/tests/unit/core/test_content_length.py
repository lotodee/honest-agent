"""parse_content_length must never hand an attacker-controlled length to int() raw."""

import pytest

from app.core.content_length import parse_content_length
from app.core.errors import BadRequestError


def test_absent_header_is_none() -> None:
    assert parse_content_length(None) is None


@pytest.mark.parametrize(
    ("value", "expected"), [("0", 0), ("10", 10), ("65536", 65536)]
)
def test_valid_lengths_parse(value: str, expected: int) -> None:
    assert parse_content_length(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "1" * 4301,  # all-digit but past CPython's 4300-digit int() limit -> ValueError
        "²",  # str.isdigit() is True, but int("²") raises
        "abc",  # not a number at all
        "",  # present but empty
        "-1",  # sign makes isdigit() False; a negative length is malformed anyway
        "12.5",  # not an integer
        " 10",  # whitespace is not part of a valid Content-Length token
    ],
)
def test_malformed_lengths_raise_bad_request(value: str) -> None:
    with pytest.raises(BadRequestError):
        parse_content_length(value)


def test_boundary_length_below_the_digit_cap_parses() -> None:
    # 20 ASCII digits is the cap; a 20-digit value must still parse, not be rejected.
    assert parse_content_length("9" * 20) == int("9" * 20)
