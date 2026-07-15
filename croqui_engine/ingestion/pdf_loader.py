from __future__ import annotations

from pathlib import Path


def _fitz():
    import fitz

    return fitz


def load_pdf_metadata(pdf_path: Path) -> dict:
    fitz = _fitz()
    with fitz.open(pdf_path) as doc:
        return {
            "path": str(pdf_path),
            "page_count": doc.page_count,
            "metadata": dict(doc.metadata or {}),
            "is_encrypted": bool(doc.is_encrypted),
        }


def get_page_count(pdf_path: Path) -> int:
    fitz = _fitz()
    with fitz.open(pdf_path) as doc:
        return doc.page_count


def get_page_text(pdf_path: Path, page_index: int) -> str:
    fitz = _fitz()
    with fitz.open(pdf_path) as doc:
        return doc[page_index].get_text() or ""


def get_all_text(pdf_path: Path) -> str:
    fitz = _fitz()
    parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            parts.append(page.get_text() or "")
    return "\n".join(parts)
