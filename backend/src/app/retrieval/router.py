"""Retrieval routes. Wired into the app under /v1; search lands with retrieval."""

from fastapi import APIRouter

router = APIRouter(prefix="/retrieval", tags=["retrieval"])
