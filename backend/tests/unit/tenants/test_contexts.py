"""The three doors must be three distinct types, never one collapsed AuthContext."""

import dataclasses

from app.tenants.contexts import (
    ExternalCallerContext,
    OwnerRequestContext,
    VisitorRequestContext,
)


def test_three_contexts_are_distinct_types() -> None:
    owner = OwnerRequestContext(tenant_id="tenant-a", user_id="user-1")
    visitor = VisitorRequestContext(tenant_id="tenant-a", query="hello")
    external = ExternalCallerContext(tenant_id="tenant-a")
    assert len({type(owner), type(visitor), type(external)}) == 3
    assert owner.tenant_id == visitor.tenant_id == external.tenant_id == "tenant-a"


def test_owner_carries_user_identity_visitor_does_not() -> None:
    owner = OwnerRequestContext(tenant_id="tenant-a", user_id="user-1")
    visitor = VisitorRequestContext(tenant_id="tenant-a", query="q")
    assert owner.user_id == "user-1"
    assert not hasattr(visitor, "user_id")


def test_visitor_context_carries_only_tenant_and_query() -> None:
    visitor = VisitorRequestContext(tenant_id="tenant-a", query="q")
    fields = {f.name for f in dataclasses.fields(visitor)}
    assert fields == {"tenant_id", "query"}


def test_contexts_are_frozen_so_tenant_cannot_be_reassigned() -> None:
    external = ExternalCallerContext(tenant_id="tenant-a")
    try:
        external.tenant_id = "tenant-b"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("context tenant_id must be immutable")
