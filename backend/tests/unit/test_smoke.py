"""Unit layer smoke test: the app factory imports and constructs."""

from fastapi import FastAPI


def test_app_factory_constructs(app: FastAPI) -> None:
    assert isinstance(app, FastAPI)
    assert app.title == "Honest Agent"
