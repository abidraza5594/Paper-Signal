from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from pathlib import Path
from .extraction.layout import PageLayout, native_layout, transcribed_layout

import fitz


class PdfProcessingError(ValueError):
    pass


@dataclass(frozen=True)
class PageText:
    number: int
    text: str
    needs_ocr: bool
    layout: PageLayout | None = None
    original_text: str | None = None
    original_layout: PageLayout | None = None


@dataclass(frozen=True)
class PdfTextResult:
    pages: list[PageText]
    metadata: dict[str, object]

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def ocr_candidates(self) -> list[int]:
        return [page.number for page in self.pages if page.needs_ocr]


class PdfTextService:
    def __init__(self, min_text_chars: int = 80, chunk_chars: int = 50_000):
        self.min_text_chars = min_text_chars
        self.chunk_chars = chunk_chars

    def extract(self, path: Path) -> PdfTextResult:
        try:
            document = fitz.open(path)
        except Exception as exc:
            raise PdfProcessingError("The PDF is corrupt or cannot be opened.") from exc

        try:
            if document.needs_pass:
                raise PdfProcessingError("Password-protected PDFs are not supported in this test build.")
            pages: list[PageText] = []
            for index, page in enumerate(document):
                text = page.get_text("text", sort=True).strip()
                layout = native_layout(page, index + 1)
                image_area = sum(fitz.Rect(box).get_area() for box in layout.image_boxes)
                pages.append(
                    PageText(
                        number=index + 1,
                        text=text,
                        needs_ocr=(len(text) < self.min_text_chars
                                   or "\ufffd" in text or bool(layout.issues)),
                        layout=layout,
                    )
                )
            metadata = {
                "page_count": len(pages),
                "title": (document.metadata or {}).get("title") or None,
                "author": (document.metadata or {}).get("author") or None,
            }
            if not pages:
                raise PdfProcessingError("The PDF does not contain any pages.")
            return PdfTextResult(pages=pages, metadata=metadata)
        finally:
            document.close()

    @staticmethod
    def inspect_page_count(path: Path) -> int:
        try:
            document = fitz.open(path)
        except Exception as exc:
            raise PdfProcessingError("The PDF is corrupt or cannot be opened.") from exc
        try:
            if document.needs_pass:
                raise PdfProcessingError("Password-protected PDFs are not supported.")
            count = document.page_count
            if count < 1:
                raise PdfProcessingError("The PDF does not contain any pages.")
            return count
        finally:
            document.close()

    @staticmethod
    def render_page_data_url(path: Path, page_number: int, dpi: int = 144, bbox=None) -> str:
        try:
            document = fitz.open(path)
        except Exception as exc:
            raise PdfProcessingError("The PDF page could not be rendered for vision.") from exc
        try:
            if page_number < 1 or page_number > document.page_count:
                raise PdfProcessingError(f"PDF page {page_number} is out of range.")
            page = document.load_page(page_number - 1)
            clip = None
            if bbox is not None:
                clip = (fitz.Rect(bbox) + (-30, -60, 30, 30)) & page.rect
            pixmap = page.get_pixmap(dpi=dpi, alpha=False, clip=clip)
            image_bytes = pixmap.tobytes("jpeg", jpg_quality=85)
            encoded = base64.b64encode(image_bytes).decode("ascii")
            return f"data:image/jpeg;base64,{encoded}"
        except PdfProcessingError:
            raise
        except Exception as exc:
            raise PdfProcessingError(
                f"PDF page {page_number} could not be rendered for vision."
            ) from exc
        finally:
            document.close()

    @staticmethod
    def apply_page_text(result: PdfTextResult, replacement_text: dict[int, str], parser: str = "vision") -> PdfTextResult:
        pages = [
            replace(
                page,
                text=replacement_text.get(page.number, page.text).strip(),
                needs_ocr=not bool(replacement_text.get(page.number, "").strip()),
                original_text=page.original_text or page.text,
                original_layout=page.original_layout or page.layout,
                layout=transcribed_layout(replacement_text[page.number], page.number, parser),
            )
            if replacement_text.get(page.number, "").strip() else page
            for page in result.pages
        ]
        return PdfTextResult(pages=pages, metadata=result.metadata)

    @staticmethod
    def apply_ocr(result: PdfTextResult, replacement_text: dict[int, str]) -> PdfTextResult:
        return PdfTextService.apply_page_text(result, replacement_text, parser="ocr")

    def to_chunks(self, result: PdfTextResult) -> list[str]:
        chunks: list[str] = []
        current = ""
        for page in result.pages:
            page_text = page.text.strip()
            if not page_text:
                continue
            block = f"\n--- PAGE {page.number} ---\n{page_text}\n"
            if len(block) > self.chunk_chars:
                if current:
                    chunks.append(current.strip())
                    current = ""
                body_limit = max(1000, self.chunk_chars - 80)
                for start in range(0, len(page_text), body_limit):
                    segment = page_text[start : start + body_limit]
                    chunks.append(
                        f"--- PAGE {page.number} (segment {start // body_limit + 1}) ---\n{segment}"
                    )
                continue
            if current and len(current) + len(block) > self.chunk_chars:
                chunks.append(current.strip())
                current = block
            else:
                current += block
        if current.strip():
            chunks.append(current.strip())
        return chunks
