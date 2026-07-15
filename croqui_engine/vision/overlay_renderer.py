from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from croqui_engine.core.models import TechnicalPayload
from croqui_engine.ingestion.page_renderer import render_page_png


def render_overlay_page(
    pdf_path: Path,
    payload: TechnicalPayload,
    page_index: int,
    output_path: Path,
    dpi: int = 150,
) -> Path:
    base_path = output_path.parent / f"_base_{page_index + 1:03d}.png"
    render_page_png(pdf_path, page_index, base_path, dpi=dpi)
    img = Image.open(base_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    scale = dpi / 72.0
    try:
        font = ImageFont.truetype("Arial.ttf", 14)
    except Exception:
        font = ImageFont.load_default()

    def box(bbox, color, label):
        if not bbox:
            return
        xy = [bbox.x0 * scale, bbox.y0 * scale, bbox.x1 * scale, bbox.y1 * scale]
        draw.rectangle(xy, outline=color, width=3)
        draw.text((xy[0] + 3, max(0, xy[1] - 16)), label, fill=color, font=font)

    for node in payload.active_nodes():
        if node.page_index == page_index:
            box(node.bbox, (31, 95, 153, 255), node.id)
    for span in payload.active_spans():
        if span.page_index == page_index:
            box(span.bbox, (53, 133, 89, 255), span.id)
    for equipment in payload.active_equipment():
        if equipment.page_index == page_index:
            box(equipment.bbox, (190, 74, 46, 255), f"{equipment.type} {equipment.code}")
    for area in payload.work_areas:
        if area.page_index == page_index:
            box(area.bbox, (214, 51, 47, 255), area.id)

    merged = Image.alpha_composite(img, overlay).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.save(output_path)
    try:
        base_path.unlink()
    except OSError:
        pass
    return output_path


def render_all_overlays(pdf_path: Path, payload: TechnicalPayload, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for page in payload.pages:
        target = output_dir / f"page_{page.index + 1:03d}.png"
        paths.append(render_overlay_page(pdf_path, payload, page.index, target))
    return paths
