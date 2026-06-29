"""Agent routes. Wired into the app under /v1; the answer route lands with the agent."""

from fastapi import APIRouter

router = APIRouter(prefix="/agent", tags=["agent"])
