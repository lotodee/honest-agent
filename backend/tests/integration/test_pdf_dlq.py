"""A poison PDF lands in a DLQ-shaped result with a reason; the batch continues."""

from pathlib import Path

import fitz
import pytest

from app.ingestion.pipeline import DocumentStatus, process_batch

pytestmark = pytest.mark.integration


def _write_text_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "A healthy page with real native text content.")
    doc.save(str(path))
    doc.close()


async def test_poison_goes_to_dlq_and_batch_continues(tmp_path: Path) -> None:
    good = tmp_path / "good.pdf"
    poison = tmp_path / "poison.pdf"
    good_after = tmp_path / "good_after.pdf"
    _write_text_pdf(good)
    poison.write_bytes(b"not a pdf at all")
    _write_text_pdf(good_after)

    results = await process_batch([good, poison, good_after])

    assert results[0].status is DocumentStatus.DONE
    assert results[1].status is DocumentStatus.DEAD
    assert results[1].failure_reason is not None
    assert "malformed" in results[1].failure_reason
    assert results[1].result is None
    # The healthy file AFTER the poison one was still processed: no silent stop.
    assert results[2].status is DocumentStatus.DONE
