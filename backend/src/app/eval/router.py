"""Eval routes. Wired into the app under /v1; result routes land with the eval layer."""

from fastapi import APIRouter

router = APIRouter(prefix="/eval", tags=["eval"])
