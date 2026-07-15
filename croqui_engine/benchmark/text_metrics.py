from __future__ import annotations

from pathlib import Path

from croqui_engine.pdf.pdf_text_compare import compare_pdf_text


def text_metrics(target_pdf: Path, generated_pdf: Path) -> dict:
    return compare_pdf_text(target_pdf, generated_pdf)

