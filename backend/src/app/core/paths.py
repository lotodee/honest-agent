"""Boundary-safe request-path prefix matching for the door middlewares.

Both body-cap gates decide "is this request under the path I guard?". A bare
`path.startswith(prefix)` also matches a SIBLING route that merely shares the string —
`startswith("/v1/tenants")` is true for `/v1/tenants2` and `/v1/tenantsinvite` — which
would silently pull a future, unrelated route into a gate never meant to guard it (or,
for the visitor gate, into its full auth chain). Matching on the path segment boundary
prevents that. Extracted so the check lives in one place, not inlined per gate.
"""


def path_under_prefix(path: str, prefix: str) -> bool:
    """True iff `path` is `prefix` itself or a segment strictly beneath it.

    The next character after `prefix` must be `/` (or `path` must equal `prefix`), so
    `/v1/tenants` matches `/v1/tenants` and `/v1/tenants/me` but NOT `/v1/tenants2`.
    """
    return path == prefix or path.startswith(prefix + "/")
