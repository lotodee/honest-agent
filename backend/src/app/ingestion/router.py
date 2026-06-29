"""Ingestion routes. Wired into the app under /v1; routes land with the worker."""

from fastapi import APIRouter

router = APIRouter(prefix="/ingestion", tags=["ingestion"])
