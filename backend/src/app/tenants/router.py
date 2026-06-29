"""Tenant routes. Wired into the app under /v1; routes land with the tenant work."""

from fastapi import APIRouter

router = APIRouter(prefix="/tenants", tags=["tenants"])
