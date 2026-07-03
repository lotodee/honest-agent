"""The per-page router: native text first, gated OCR next, Gemini vision last.

Escalation is strictly cost-ordered. Native text is free. OCR is ~1000x slower, so
it is gated behind a binary scanned-page heuristic. A Gemini vision call costs real
tokens, so image/vector pages are rendered at a deliberately low DPI (a higher
render just spends tokens Gemini tiles away) and content-hash deduped so an
identical page image is described once, never paid for twice (Delta 4).

The OCR and vision runners are injected so the routing DECISION is unit-testable
with fakes, while the real Tesseract and Gemini paths run in integration.
"""

import hashlib
import os
from collections.abc import Callable

import fitz

from app.core.settings import Settings
from app.ingestion.pdf.models import PageContent, PageSource

# A page with fewer than this many non-whitespace characters counts as near-empty
# text, the first half of the scanned-page heuristic.
NATIVE_TEXT_MIN_CHARS = 20
# Image bounding boxes covering at least this fraction of the page rect is the
# second half: near-empty text PLUS ~95% image coverage means a scanned page.
SCANNED_IMAGE_COVERAGE = 0.95
# 150 DPI is the deliberate low-end render for both OCR and vision: enough to read,
# low enough that Gemini does not tile and discard the extra pixels (Delta 4).
OCR_DPI = 150
VISION_RENDER_DPI = 150

OcrRunner = Callable[[fitz.Page], str]
VisionDescriber = Callable[[bytes], str]


def route_page(
    page: fitz.Page,
    *,
    run_ocr: OcrRunner,
    describe_vision: VisionDescriber,
    cache: dict[str, str],
) -> PageContent:
    text = page.get_text().strip()
    if len(text) >= NATIVE_TEXT_MIN_CHARS:
        return PageContent(page_index=page.number, text=text, source=PageSource.NATIVE)
    if _image_coverage(page) >= SCANNED_IMAGE_COVERAGE:
        return PageContent(
            page_index=page.number, text=run_ocr(page), source=PageSource.OCR
        )
    image = _render_downsampled(page)
    digest = hashlib.sha256(image).hexdigest()
    description = cache.get(digest)
    if description is None:
        description = describe_vision(image)
        cache[digest] = description
    return PageContent(
        page_index=page.number, text=description, source=PageSource.VISION
    )


def _image_coverage(page: fitz.Page) -> float:
    page_area = abs(page.rect)
    if page_area <= 0:
        return 0.0
    covered = sum(abs(fitz.Rect(info["bbox"])) for info in page.get_image_info())
    return float(min(covered / page_area, 1.0))


def _render_downsampled(page: fitz.Page) -> bytes:
    pixmap = page.get_pixmap(dpi=VISION_RENDER_DPI)
    return bytes(pixmap.tobytes("png"))


def run_ocr_tesseract(page: fitz.Page) -> str:
    """Real OCR via PyMuPDF's Tesseract integration. Integration path, not unit."""
    textpage = page.get_textpage_ocr(
        flags=0, language="eng", dpi=OCR_DPI, full=True, tessdata=_resolve_tessdata()
    )
    return str(page.get_text(textpage=textpage)).strip()


def _resolve_tessdata() -> str:
    env = os.environ.get("TESSDATA_PREFIX")
    if env:
        return env
    for candidate in (
        "/usr/local/share/tessdata",
        "/opt/homebrew/share/tessdata",
        "/usr/share/tesseract-ocr/5/tessdata",
        "/usr/share/tessdata",
    ):
        if os.path.isdir(candidate):
            return candidate
    raise RuntimeError("tessdata directory not found; set TESSDATA_PREFIX")


class StubVisionDescriber:
    """Day-3 stand-in for the Gemini vision call. The model name still comes from
    Settings (Delta 4), so the seam is real; the live GoogleModel call is wired on
    Day 5 when Vertex credentials are provisioned.
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def __call__(self, image: bytes) -> str:
        digest = hashlib.sha256(image).hexdigest()[:12]
        return (
            f"[stub vision description of page image {digest}; a real "
            f"{self.model_name} call needs Vertex credentials]"
        )


def build_vision_describer(settings: Settings) -> VisionDescriber:
    # The model name always comes from Settings. Day 3 ships the stub because Vertex
    # credentials are not provisioned here; the real call lands on Day 5.
    return StubVisionDescriber(model_name=settings.generation_model)
