import fitz

from app.pdf_service import PdfTextService


def make_pdf(path, pages):
    document = fitz.open()
    for content in pages:
        page = document.new_page()
        page.insert_text((72, 72), content)
    document.save(path)
    document.close()


def test_extracts_page_text_and_detects_ocr_candidates(tmp_path):
    path = tmp_path / "document.pdf"
    make_pdf(path, ["This is a readable digital page with enough text for local extraction.", "x"])
    service = PdfTextService(min_text_chars=20, chunk_chars=1000)

    result = service.extract(path)

    assert result.page_count == 2
    assert result.pages[0].needs_ocr is False
    assert result.pages[1].needs_ocr is True
    assert result.ocr_candidates == [2]


def test_chunks_keep_page_markers(tmp_path):
    path = tmp_path / "document.pdf"
    make_pdf(path, ["Alpha " * 30, "Beta " * 30])
    service = PdfTextService(min_text_chars=5, chunk_chars=180)

    chunks = service.to_chunks(service.extract(path))

    assert len(chunks) >= 2
    assert any("PAGE 1" in chunk for chunk in chunks)
    assert any("PAGE 2" in chunk for chunk in chunks)


def test_page_can_be_rendered_for_vision(tmp_path):
    path = tmp_path / "vision.pdf"
    make_pdf(path, ["Visible text"])

    image = PdfTextService.render_page_data_url(path, 1, dpi=96)

    assert image.startswith("data:image/jpeg;base64,")
    assert len(image) > 100
