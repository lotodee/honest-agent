"""Generate the four Day-3 PDF fixtures ONCE, then commit the static files.

The tests read the committed .pdf files; they never regenerate at run time (that
would make CI depend on rasterization/encryption libraries and can flake). Re-run
this only to deliberately refresh the fixtures:

    uv run python tests/fixtures/pdf/generate_fixtures.py
"""

import pathlib

import fitz

HERE = pathlib.Path(__file__).resolve().parent

# The known text baked into the scanned image, so the OCR assertion knows the
# answer. Uppercase and spaced for reliable recognition.
SCANNED_TEXT = "INVOICE 2026 TOTAL DUE 4200 USD"
ENCRYPTED_PASSWORD = "user-secret-123"  # noqa: S105  fixture password, not a real secret


def _scanned_image_pdf(path: pathlib.Path) -> None:
    # A small grayscale render keeps the committed fixture tiny while staying
    # readable to OCR (100 DPI of 26pt text is ample).
    source = fitz.open()
    source_page = source.new_page(width=460, height=150)
    source_page.insert_text((20, 90), SCANNED_TEXT, fontsize=26)
    pixmap = source_page.get_pixmap(dpi=100, colorspace=fitz.csGRAY)
    source.close()

    out = fitz.open()
    page = out.new_page(width=460, height=150)
    page.insert_image(page.rect, pixmap=pixmap)  # full-page image, no text layer
    out.save(str(path))
    out.close()


def _diagram_pdf(path: pathlib.Path) -> None:
    out = fitz.open()
    page = out.new_page()
    # A vector flowchart with no text layer: OCR cannot serve it, so it routes to
    # vision.
    page.draw_rect(
        fitz.Rect(120, 100, 300, 170), color=(0, 0, 0), fill=(0.8, 0.9, 1), width=2
    )
    page.draw_rect(
        fitz.Rect(120, 320, 300, 390), color=(0, 0, 0), fill=(0.9, 1, 0.85), width=2
    )
    page.draw_line((210, 170), (210, 320))
    page.draw_circle((210, 245), 12, color=(1, 0, 0), fill=(1, 0.7, 0.7))
    out.save(str(path))
    out.close()


def _encrypted_pdf(path: pathlib.Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "confidential content behind a password")
    doc.save(
        str(path),
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw=ENCRYPTED_PASSWORD,
    )
    doc.close()


def _poison_pdf(path: pathlib.Path) -> None:
    # A real PDF truncated mid-stream: the header survives but the xref, trailer,
    # and later objects are gone, so the parser cannot open or repair it.
    valid = fitz.open()
    valid.new_page().insert_text((72, 72), "this document is truncated mid-stream")
    data = valid.tobytes()
    valid.close()
    path.write_bytes(data[: len(data) // 3])


def main() -> None:
    _scanned_image_pdf(HERE / "scanned.pdf")
    _diagram_pdf(HERE / "diagram.pdf")
    _encrypted_pdf(HERE / "encrypted.pdf")
    _poison_pdf(HERE / "poison.pdf")
    print(f"wrote fixtures to {HERE}")


if __name__ == "__main__":
    main()
