"""The subprocess crash boundary: a poison PDF kills the child, the parent survives.

These run in integration because they spawn a real child process. Fixtures are tiny
temp PDFs generated in-test to exercise the mechanism; the committed real-file proof
lives in test_pdf_spike.py.
"""

from collections.abc import Callable
from pathlib import Path

import fitz
import pytest

from app.ingestion.errors import PoisonDocumentError
from app.ingestion.pdf.isolate import extract_isolated
from app.ingestion.pdf.models import PageSource

pytestmark = pytest.mark.integration


def _write_encrypted_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "secret contents behind a password")
    doc.save(
        str(path),
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="user-secret",
    )
    doc.close()


async def test_wellformed_pdf_extracts_native_text(
    tmp_path: Path, make_text_pdf: Callable[[Path], None]
) -> None:
    good = tmp_path / "good.pdf"
    make_text_pdf(good)
    result = await extract_isolated(good)
    assert result.page_count == 1
    assert result.pages[0].source is PageSource.NATIVE
    assert "native text" in result.pages[0].text


async def test_malformed_pdf_is_poison_and_parent_survives(
    tmp_path: Path, make_text_pdf: Callable[[Path], None]
) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"this is definitely not a valid pdf file")
    with pytest.raises(PoisonDocumentError) as caught:
        await extract_isolated(bad)
    assert "malformed" in caught.value.reason

    # The parent was never at risk: it processes a healthy file immediately after.
    good = tmp_path / "good.pdf"
    make_text_pdf(good)
    result = await extract_isolated(good)
    assert result.page_count == 1


async def test_encrypted_pdf_reported_distinctly(tmp_path: Path) -> None:
    enc = tmp_path / "enc.pdf"
    _write_encrypted_pdf(enc)
    with pytest.raises(PoisonDocumentError) as caught:
        await extract_isolated(enc)
    assert caught.value.reason == "encrypted"


async def test_timeout_is_reported_as_poison(
    tmp_path: Path, make_text_pdf: Callable[[Path], None]
) -> None:
    good = tmp_path / "good.pdf"
    make_text_pdf(good)
    with pytest.raises(PoisonDocumentError) as caught:
        await extract_isolated(good, timeout_s=0.001)
    assert caught.value.reason == "extraction timeout"
