"""Guardrail routes. Wired into the app under /v1; checks land with the guardrails."""

from fastapi import APIRouter

router = APIRouter(prefix="/guardrails", tags=["guardrails"])
