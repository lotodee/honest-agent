"""The Day-3 spike proven against the committed REAL fixtures, end to end.

Scanned image -> real OCR text; vector diagram -> a vision description; a truncated
PDF and an encrypted PDF -> DLQ-shaped results with distinct reasons. The tests read
the static fixture files; they never regenerate them (see generate_fixtures.py).
"""

from pathlib import Path

import pytest

from app.ingestion.pdf.models import PageSource
from app.ingestion.pipeline import DocumentStatus, process_document

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "pdf"


async def test_scanned_pdf_becomes_searchable_text() -> None:
    processed = await process_document(FIXTURES / "scanned.pdf")
    assert processed.status is DocumentStatus.DONE
    assert processed.result is not None
    page = processed.result.pages[0]
    assert page.source is PageSource.OCR
    # OCR recovers the text baked into the image (allowing minor character noise).
    assert "INVOICE" in page.text.upper()
    assert "4200" in page.text


async def test_diagram_pdf_becomes_a_retrievable_description() -> None:
    processed = await process_document(FIXTURES / "diagram.pdf")
    assert processed.status is DocumentStatus.DONE
    assert processed.result is not None
    page = processed.result.pages[0]
    assert page.source is PageSource.VISION
    assert page.text  # a description (a stub here; real Gemini call is Day 5)


async def test_poison_pdf_is_dead_with_a_malformed_reason() -> None:
    processed = await process_document(FIXTURES / "poison.pdf")
    assert processed.status is DocumentStatus.DEAD
    assert processed.failure_reason is not None
    assert "malformed" in processed.failure_reason


async def test_encrypted_pdf_is_dead_with_an_encrypted_reason() -> None:
    processed = await process_document(FIXTURES / "encrypted.pdf")
    assert processed.status is DocumentStatus.DEAD
    assert processed.failure_reason == "encrypted"
