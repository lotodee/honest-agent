"""Child-process PDF extractor: `python -m app.ingestion.pdf.extract <pdf_path>`.

Runs in its own process so a poison PDF that segfaults PyMuPDF's C library kills
only THIS process, never the worker. It prints exactly one ExtractionEnvelope JSON
to stdout and nothing else, so the parent can parse the outcome unambiguously.

Classified, catchable failures (encrypted, malformed) exit 0 with an ok=false
envelope; a true uncatchable crash is a non-zero or signal exit with no envelope,
which the parent turns into its own poison reason.
"""

import sys

import fitz

from app.core.settings import get_settings
from app.ingestion.pdf.models import (
    ExtractionFailure,
    ExtractionOk,
    ExtractionResult,
)
from app.ingestion.pdf.router import (
    build_vision_describer,
    route_page,
    run_ocr_tesseract,
)


def extract(pdf_path: str) -> ExtractionOk | ExtractionFailure:
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:  # noqa: BLE001  fitz.open surfaces many C-library errors on a poison file; any of them means "cannot parse"
        # Only the exception TYPE name is recorded, never the message or file
        # content, so the DLQ reason cannot leak document contents.
        return ExtractionFailure(reason=f"malformed: {type(exc).__name__}")
    try:
        if doc.needs_pass:
            return ExtractionFailure(reason="encrypted")
        describe_vision = build_vision_describer(get_settings())
        cache: dict[str, str] = {}
        try:
            pages = [
                route_page(
                    page,
                    run_ocr=run_ocr_tesseract,
                    describe_vision=describe_vision,
                    cache=cache,
                )
                for page in doc
            ]
        except Exception as exc:  # noqa: BLE001  a catchable per-page parse failure is still a poison document
            return ExtractionFailure(reason=f"malformed: {type(exc).__name__}")
        return ExtractionOk(
            result=ExtractionResult(page_count=doc.page_count, pages=pages)
        )
    finally:
        doc.close()


def main() -> None:
    if len(sys.argv) != 2:
        sys.stdout.write(
            ExtractionFailure(reason="usage: extract <pdf_path>").model_dump_json()
        )
        raise SystemExit(2)
    sys.stdout.write(extract(sys.argv[1]).model_dump_json())


if __name__ == "__main__":
    main()
