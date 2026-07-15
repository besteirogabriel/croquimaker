from __future__ import annotations

from pathlib import Path

from croqui_engine.pdf.pdf_visual_compare import compare_pdf_visual


def visual_metrics(target_pdf: Path, generated_pdf: Path, output_dir: Path) -> dict:
    return compare_pdf_visual(target_pdf, generated_pdf, output_dir)

