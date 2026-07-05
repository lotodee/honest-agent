"""path_under_prefix matches on the segment boundary, not a bare string prefix."""

import pytest

from app.core.paths import path_under_prefix

_PREFIX = "/v1/tenants"


@pytest.mark.parametrize(
    "path", ["/v1/tenants", "/v1/tenants/", "/v1/tenants/me", "/v1/tenants/a/b"]
)
def test_prefix_itself_and_real_sub_paths_match(path: str) -> None:
    assert path_under_prefix(path, _PREFIX)


@pytest.mark.parametrize(
    "path",
    ["/v1/tenants2", "/v1/tenantsinvite", "/v1/tenant", "/v1", "/v2/tenants", "/", ""],
)
def test_sibling_and_unrelated_paths_do_not_match(path: str) -> None:
    # These share the string but are not a segment under the prefix; a bare startswith
    # would wrongly match the first two.
    assert not path_under_prefix(path, _PREFIX)
