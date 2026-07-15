from __future__ import annotations

from pathlib import Path

from croqui_engine.core.models import BBox, ExtractedWord, TextBlock


def extract_words(pdf_path: Path, page_index: int) -> list[ExtractedWord]:
    import fitz

    words: list[ExtractedWord] = []
    with fitz.open(pdf_path) as doc:
        page = doc[page_index]
        for item in page.get_text("words"):
            x0, y0, x1, y1, text = item[:5]
            block_no = int(item[5]) if len(item) > 5 else None
            line_no = int(item[6]) if len(item) > 6 else None
            word_no = int(item[7]) if len(item) > 7 else None
            words.append(
                ExtractedWord(
                    text=str(text),
                    page_index=page_index,
                    bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1),
                    block_no=block_no,
                    line_no=line_no,
                    word_no=word_no,
                )
            )
    return words


def extract_text_blocks(pdf_path: Path, page_index: int) -> list[TextBlock]:
    import fitz

    blocks: list[TextBlock] = []
    with fitz.open(pdf_path) as doc:
        page = doc[page_index]
        for block_no, block in enumerate(page.get_text("blocks")):
            x0, y0, x1, y1, text = block[:5]
            if not str(text).strip():
                continue
            blocks.append(
                TextBlock(
                    text=str(text).strip(),
                    page_index=page_index,
                    bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1),
                    block_no=block_no,
                )
            )
    return blocks


def merge_text_lines(words: list[ExtractedWord]) -> list[str]:
    grouped: dict[tuple[int, int | None, int | None], list[ExtractedWord]] = {}
    for word in words:
        key = (word.page_index, word.block_no, word.line_no)
        grouped.setdefault(key, []).append(word)

    lines: list[str] = []
    for key in sorted(grouped):
        row = sorted(grouped[key], key=lambda w: w.bbox.x0)
        text = " ".join(w.text for w in row).strip()
        if text:
            lines.append(text)
    return lines
