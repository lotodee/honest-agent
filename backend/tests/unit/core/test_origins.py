"""Exact-host Origin matching: the subdomain and substring tricks must not pass."""

from app.core.origins import host_allowed, origin_host

ALLOWED = frozenset({"allowed.com", "tenant-a.example.com", "localhost"})


def test_exact_host_allowed() -> None:
    assert host_allowed("https://allowed.com", ALLOWED)
    assert host_allowed("https://tenant-a.example.com", ALLOWED)


def test_case_insensitive_host() -> None:
    assert host_allowed("https://Allowed.com", ALLOWED)


def test_port_does_not_change_the_host() -> None:
    assert host_allowed("https://allowed.com:8443", ALLOWED)


def test_trailing_dot_is_stripped() -> None:
    assert host_allowed("https://allowed.com.", ALLOWED)


def test_subdomain_suffix_attack_rejected() -> None:
    assert not host_allowed("https://allowed.com.evil.com", ALLOWED)


def test_prefix_attack_rejected() -> None:
    assert not host_allowed("https://evil-allowed.com", ALLOWED)
    assert not host_allowed("https://allowed.com.attacker.net", ALLOWED)


def test_www_is_a_distinct_host() -> None:
    assert not host_allowed("https://www.allowed.com", ALLOWED)


def test_null_and_empty_and_schemeless_are_rejected() -> None:
    assert not host_allowed("null", ALLOWED)
    assert not host_allowed("", ALLOWED)
    assert not host_allowed("   ", ALLOWED)
    assert not host_allowed("allowed.com", ALLOWED)  # no scheme, no host parsed


def test_origin_host_extraction() -> None:
    assert origin_host("https://allowed.com:8443/path") == "allowed.com"
    assert origin_host("null") is None
    assert origin_host("") is None
