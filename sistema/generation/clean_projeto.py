from __future__ import annotations

import json
from pathlib import Path

import fitz

from sistema.extractors._pdf_geometry import classify_conductor_color
from sistema.parsing.entities import ProjectExtraction

MT_COLOR = (0, 0, 1)
BT_COLOR = (0, 0.6, 0)
MARK_COLOR = (0, 0, 0)


def _mark(page: fitz.Page, x: float, y_pdf: float) -> None:
    page.draw_circle((x, y_pdf), 3, color=MARK_COLOR, width=0.75)


def render_clean_projeto(
    source_path: Path,
    extraction: ProjectExtraction,
    out_path: Path,
    *,
    inventory_path: Path | None = None,
    png_path: Path | None = None,
) -> Path:
    """Mantem somente condutores CAD e marcadores de postes."""

    src = fitz.open(source_path)
    out = fitz.open()
    try:
        page_heights: dict[int, float] = {}
        for page_no in range(src.page_count):
            src_page = src[page_no]
            page_heights[page_no] = src_page.rect.height
            new_page = out.new_page(width=src_page.rect.width, height=src_page.rect.height)

            for drawing in src_page.get_drawings():
                if drawing.get("type") not in ("s", "fs"):
                    continue
                tensao = classify_conductor_color(drawing.get("color"))
                if tensao is None:
                    continue
                color = MT_COLOR if tensao == "MT" else BT_COLOR
                for item in drawing.get("items", []):
                    if item[0] == "l":
                        new_page.draw_line(item[1], item[2], color=color, width=1)

        def mark_position(position) -> None:
            if position is None or position.page not in page_heights:
                return
            _mark(out[position.page], position.x, position.y_pdf(page_heights[position.page]))

        # Postes recebem apenas o marcador. Codigos sequenciais nao sao rotulos
        # reais do projeto e por isso nao sao impressos.
        for pole in extraction.poles:
            mark_position(pole.position)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out.save(str(out_path))
    finally:
        out.close()
        src.close()

    if inventory_path:
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(
            json.dumps(extraction.color_inventory, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if png_path:
        clean = fitz.open(out_path)
        try:
            pix = clean[0].get_pixmap(dpi=120, alpha=False)
            png_path.parent.mkdir(parents=True, exist_ok=True)
            pix.save(str(png_path))
        finally:
            clean.close()
    return out_path
