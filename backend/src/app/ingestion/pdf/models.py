"""Typed shapes crossing the subprocess boundary. Extraction produces text per page.

Day 3 proves EXTRACTION only: each page becomes retrievable text (native, OCR, or a
vision description). Turning that into chunks and vectors is Day 4/5, not here.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class PageSource(StrEnum):
    """Which route produced a page's text. Useful for the proof and for debugging."""

    NATIVE = "native"
    OCR = "ocr"
    VISION = "vision"


class PageContent(BaseModel):
    page_index: int
    text: str
    source: PageSource


class ExtractionResult(BaseModel):
    page_count: int
    pages: list[PageContent]


class ExtractionOk(BaseModel):
    ok: Literal[True] = True
    result: ExtractionResult


class ExtractionFailure(BaseModel):
    """A CATCHABLE, classified failure (encrypted, malformed). The child exits 0 with
    this envelope; a true uncatchable crash is a non-zero/signal exit with no envelope.
    """

    ok: Literal[False] = False
    reason: str


# The child prints exactly one of these as JSON on stdout.
ExtractionEnvelope = Annotated[
    ExtractionOk | ExtractionFailure, Field(discriminator="ok")
]
