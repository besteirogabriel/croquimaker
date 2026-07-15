from __future__ import annotations

from pathlib import Path

from croqui_engine.core.models import PageInfo
from croqui_engine.extraction.text_extractor import extract_text_blocks, extract_words
from croqui_engine.extraction.vector_extractor import extract_drawings
from croqui_engine.ingestion.pdf_loader import load_pdf_metadata
from croqui_engine.storage.file_store import write_json


def extract_raw_document(pdf_path: Path, pages: list[PageInfo], output_path: Path | None = None) -> dict:
    words = []
    blocks = []
    drawings = []

    for page in pages:
        page_words = extract_words(pdf_path, page.index)
        page_blocks = extract_text_blocks(pdf_path, page.index)
        page_drawings = extract_drawings(pdf_path, page.index)
        words.extend(item.as_dict() for item in page_words)
        blocks.extend(item.as_dict() for item in page_blocks)
        drawings.extend(item.as_dict() for item in page_drawings)

    raw = {
        "pdf": load_pdf_metadata(pdf_path),
        "pages": [page.as_dict() for page in pages],
        "words": words,
        "blocks": blocks,
        "drawings": drawings,
    }
    if output_path:
        write_json(output_path, raw)
    return raw
