"""Spike-shaped document processing: extract, or route poison to a DLQ result.

This is the honest Day-3 stand-in for Day 4's real job table and queue. It carries
no tenant id (this spike operates on a file path only) and writes NO rows into the
Day-2 documents/chunks tables; a poison outcome is a typed in-memory record whose
shape Day 4's `dead` job row will consume. Poison is deterministic, so it is
TERMINAL on the first attempt, never retried (retrying a file that breaks the parser
just wastes attempts); Day 4's retry loop is for TRANSIENT failures only.
"""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from app.ingestion.errors import PoisonDocumentError
from app.ingestion.pdf.isolate import extract_isolated
from app.ingestion.pdf.models import ExtractionResult


class DocumentStatus(StrEnum):
    DONE = "done"
    DEAD = "dead"


class ProcessedDocument(BaseModel):
    path: str
    status: DocumentStatus
    result: ExtractionResult | None = None
    failure_reason: str | None = None


async def process_document(
    pdf_path: Path, *, timeout_s: float = 60.0
) -> ProcessedDocument:
    try:
        result = await extract_isolated(pdf_path, timeout_s=timeout_s)
    except PoisonDocumentError as exc:
        return ProcessedDocument(
            path=str(pdf_path),
            status=DocumentStatus.DEAD,
            failure_reason=exc.reason,
        )
    return ProcessedDocument(
        path=str(pdf_path), status=DocumentStatus.DONE, result=result
    )


async def process_batch(
    pdf_paths: list[Path], *, timeout_s: float = 60.0
) -> list[ProcessedDocument]:
    # A poison file lands in its DLQ-shaped result and processing continues; one bad
    # file never stops the batch.
    return [await process_document(path, timeout_s=timeout_s) for path in pdf_paths]
