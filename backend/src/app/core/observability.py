"""Logfire and Sentry init, wired from Settings and inert until their keys exist."""

import logfire
import sentry_sdk
from fastapi import FastAPI

from app.core.settings import Settings

_SENTRY_TRACES_SAMPLE_RATE = 0.05


def configure_observability(app: FastAPI, settings: Settings) -> None:
    if settings.logfire_token is not None:
        logfire.configure(token=settings.logfire_token)
        logfire.instrument_fastapi(app)
    if settings.sentry_dsn is not None:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=_SENTRY_TRACES_SAMPLE_RATE,
        )
