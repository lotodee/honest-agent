"""The parent side of the crash boundary: run extraction in a timeout-bounded child.

A poison PDF kills the CHILD; the parent sees a timeout, a non-zero/signal exit, or
a classified failure envelope, and turns each into a typed PoisonDocumentError with
a distinct reason. The parent process is never at risk, so the worker survives.
"""

import asyncio
import sys
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.ingestion.errors import PoisonDocumentError
from app.ingestion.pdf.models import (
    ExtractionEnvelope,
    ExtractionFailure,
    ExtractionOk,
    ExtractionResult,
)

_EXTRACTOR_MODULE = "app.ingestion.pdf.extract"
_ENVELOPE_ADAPTER: TypeAdapter[ExtractionOk | ExtractionFailure] = TypeAdapter(
    ExtractionEnvelope
)


async def extract_isolated(
    pdf_path: Path, *, timeout_s: float = 60.0
) -> ExtractionResult:
    # exec, not shell: the path is one argv element, so a crafted filename can never
    # be interpreted as a shell command.
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        _EXTRACTOR_MODULE,
        str(pdf_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise PoisonDocumentError("extraction timeout") from None

    envelope = _parse_envelope(stdout)
    if envelope is None:
        # No parseable envelope: a true uncatchable crash (segfault -> signal exit)
        # or an unexpected exit. Name the exit code, never a raw child stack trace.
        raise PoisonDocumentError(f"extractor exited {proc.returncode}")
    if isinstance(envelope, ExtractionOk):
        return envelope.result
    raise PoisonDocumentError(envelope.reason)


def _parse_envelope(stdout: bytes) -> ExtractionEnvelope | None:
    try:
        return _ENVELOPE_ADAPTER.validate_json(stdout)
    except ValidationError:
        return None
