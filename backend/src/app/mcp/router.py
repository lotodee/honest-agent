"""MCP routes. Wired into the app under /v1; the Streamable-HTTP server lands here."""

from fastapi import APIRouter

router = APIRouter(prefix="/mcp", tags=["mcp"])
