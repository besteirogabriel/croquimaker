"""Standalone reference output (separate from the generated croqui): redraws
the PROJETO PDF keeping only what matters for the network -- conductor lines
classified by their real CAD color (azul=MT, verde=BT, confirmed against a
real project) and markers at every known pole/transformer/structure/
equipment position -- dropping the basemap, dimension lines, tables and
other CAD clutter that make the original hard to read at a glance.
"""

from __future__ import annotations

from pathlib import Path

import fitz

from sistema.extractors._pdf_geometry import classify_conductor_color
from sistema.parsing.entities import ProjectExtraction

MT_COLOR = (0, 0, 1)
BT_COLOR = (0, 0.6, 0)
MARK_COLOR = (0, 0, 0)


def _mark(page: fitz.Page, x: float, y_pdf: float, label: str) -> None:
    page.draw_circle((x, y_pdf), 3, color=MARK_COLOR, width=0.75)
    if label:
        page.insert_text((x + 4, y_pdf - 4), label, fontsize=6, color=MARK_COLOR)


def render_clean_projeto(source_path: Path, extraction: ProjectExtraction, out_path: Path) -> Path:
    src = fitz.open(source_path)
    out = fitz.open()

    page_heights: dict[int, float] = {}
    for page_no in range(src.page_count):
        src_page = src[page_no]
        page_heights[page_no] = src_page.rect.height
        new_page = out.new_page(width=src_page.rect.width, height=src_page.rect.height)

        for d in src_page.get_drawings():
            if d.get("type") not in ("s", "fs"):
                continue
            tensao = classify_conductor_color(d.get("color"))
            if tensao is None:
                continue
            color = MT_COLOR if tensao == "MT" else BT_COLOR
            for item in d.get("items", []):
                if item[0] == "l":
                    p1, p2 = item[1], item[2]
                    new_page.draw_line(p1, p2, color=color, width=1)

    def _mark_position(position, label: str) -> None:
        if position is None or position.page not in page_heights:
            return
        page = out[position.page]
        y_pdf = page_heights[position.page] - position.y
        _mark(page, position.x, y_pdf, label)

    for pole in extraction.poles:
        _mark_position(pole.position, pole.codigo)
    for t in extraction.transformers:
        _mark_position(t.position, t.numero)
    for s in extraction.structure_types:
        _mark_position(s.position, s.codigo)
    for e in extraction.existing_equipment:
        _mark_position(e.position, e.numero)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(str(out_path))
    out.close()
    src.close()
    return out_path
