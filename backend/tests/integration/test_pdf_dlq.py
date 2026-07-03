"""A poison PDF lands in a DLQ-shaped result with a reason; the batch continues."""

from collections.abc import Callable
from pathlib import Path

import pytest

from app.ingestion.pipeline import DocumentStatus, process_batch

pytestmark = pytest.mark.integration


async def test_poison_goes_to_dlq_and_batch_continues(
    tmp_path: Path, make_text_pdf: Callable[[Path], None]
) -> None:
    good = tmp_path / "good.pdf"
    poison = tmp_path / "poison.pdf"
    good_after = tmp_path / "good_after.pdf"
    make_text_pdf(good)
    poison.write_bytes(b"not a pdf at all")
    make_text_pdf(good_after)

    results = await process_batch([good, poison, good_after])

    assert results[0].status is DocumentStatus.DONE
    assert results[1].status is DocumentStatus.DEAD
    assert results[1].failure_reason is not None
    assert "malformed" in results[1].failure_reason
    assert results[1].result is None
    # The healthy file AFTER the poison one was still processed: no silent stop.
    assert results[2].status is DocumentStatus.DONE
