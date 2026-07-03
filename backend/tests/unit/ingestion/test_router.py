"""The per-page router escalates native -> OCR -> vision, and dedupes vision calls."""

import fitz

from app.ingestion.pdf.models import PageSource
from app.ingestion.pdf.router import route_page


def _forbidden_ocr(page: fitz.Page) -> str:
    raise AssertionError("OCR must not run for this page")


def _forbidden_vision(image: bytes) -> str:
    raise AssertionError("vision must not run for this page")


class _CountingVision:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, image: bytes) -> str:
        self.calls += 1
        return f"description-{self.calls}"


def _native_page(doc: fitz.Document) -> fitz.Page:
    page = doc.new_page()
    page.insert_text((72, 72), "This page has plenty of real, extractable native text.")
    return page


def _scanned_page(doc: fitz.Document) -> fitz.Page:
    # A full-page image with no text layer: near-empty text plus ~100% coverage.
    page = doc.new_page()
    source = fitz.open()
    source_page = source.new_page()
    source_page.insert_text((72, 72), "SCANNED IMAGE TEXT")
    pixmap = source_page.get_pixmap(dpi=150)
    source.close()
    page.insert_image(page.rect, pixmap=pixmap)
    return page


def _vector_page(doc: fitz.Document) -> fitz.Page:
    # Vector shapes, no text, no images: OCR cannot serve it, so it goes to vision.
    page = doc.new_page()
    page.draw_rect(fitz.Rect(100, 100, 300, 300), color=(0, 0, 1), width=2)
    page.draw_line((100, 100), (300, 300))
    return page


def test_native_text_page_takes_native_path_only() -> None:
    doc = fitz.open()
    content = route_page(
        _native_page(doc),
        run_ocr=_forbidden_ocr,
        describe_vision=_forbidden_vision,
        cache={},
    )
    assert content.source is PageSource.NATIVE
    assert "native text" in content.text
    doc.close()


def test_scanned_page_takes_ocr_path() -> None:
    doc = fitz.open()
    content = route_page(
        _scanned_page(doc),
        run_ocr=lambda page: "recovered ocr text",
        describe_vision=_forbidden_vision,
        cache={},
    )
    assert content.source is PageSource.OCR
    assert content.text == "recovered ocr text"
    doc.close()


def test_vector_page_takes_vision_path() -> None:
    doc = fitz.open()
    vision = _CountingVision()
    content = route_page(
        _vector_page(doc),
        run_ocr=_forbidden_ocr,
        describe_vision=vision,
        cache={},
    )
    assert content.source is PageSource.VISION
    assert vision.calls == 1
    doc.close()


def test_identical_page_images_are_described_once() -> None:
    doc = fitz.open()
    vision = _CountingVision()
    cache: dict[str, str] = {}
    first = route_page(
        _vector_page(doc), run_ocr=_forbidden_ocr, describe_vision=vision, cache=cache
    )
    second = route_page(
        _vector_page(doc), run_ocr=_forbidden_ocr, describe_vision=vision, cache=cache
    )
    assert first.source is second.source is PageSource.VISION
    # The second identical page image is served from the dedupe cache, not paid for.
    assert vision.calls == 1
    assert first.text == second.text
    doc.close()
