from __future__ import annotations

from pathlib import Path

from croqui_engine.core.models import BBox, DrawingPrimitive


def extract_drawings(pdf_path: Path, page_index: int) -> list[DrawingPrimitive]:
    import fitz

    primitives: list[DrawingPrimitive] = []
    with fitz.open(pdf_path) as doc:
        page = doc[page_index]
        for drawing in page.get_drawings():
            primitives.extend(_normalize_drawing(drawing, page_index))
    return primitives


def _normalize_drawing(drawing: dict, page_index: int) -> list[DrawingPrimitive]:
    rect = drawing.get("rect")
    bbox = None
    if rect is not None:
        bbox = BBox(x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1)

    stroke = _color_tuple(drawing.get("color"))
    fill = _color_tuple(drawing.get("fill"))
    width = drawing.get("width")
    dash = _dash_values(drawing.get("dashes"))
    raw_type = str(drawing.get("type", ""))
    items = drawing.get("items", []) or []

    output: list[DrawingPrimitive] = []
    for item in items:
        kind = item[0] if item else "unknown"
        points = _points_from_item(item)
        primitive_type = _primitive_type(kind, points, bbox)
        output.append(
            DrawingPrimitive(
                type=primitive_type,
                page_index=page_index,
                points=points,
                stroke_color=stroke,
                fill_color=fill,
                width=width,
                dash=dash,
                bbox=bbox,
                raw_type=raw_type,
            )
        )

    if not output and bbox is not None:
        output.append(
            DrawingPrimitive(
                type="rect",
                page_index=page_index,
                points=[],
                stroke_color=stroke,
                fill_color=fill,
                width=width,
                dash=dash,
                bbox=bbox,
                raw_type=raw_type,
            )
        )
    return output


def _points_from_item(item) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for value in item[1:]:
        if hasattr(value, "x") and hasattr(value, "y"):
            pts.append((float(value.x), float(value.y)))
        elif isinstance(value, (tuple, list)) and len(value) >= 2:
            try:
                pts.append((float(value[0]), float(value[1])))
            except (TypeError, ValueError):
                pass
    return pts


def _primitive_type(kind: str, points: list[tuple[float, float]], bbox: BBox | None) -> str:
    if kind == "l" and len(points) >= 2:
        return "line"
    if kind == "re":
        if bbox and abs((bbox.x1 - bbox.x0) - (bbox.y1 - bbox.y0)) < 4:
            return "circle_like"
        return "rect"
    if kind in {"c", "qu"}:
        return "curve"
    if len(points) > 2:
        return "polyline"
    return "unknown"


def _color_tuple(value) -> tuple[float, float, float] | None:
    if not value:
        return None
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return None


def _dash_values(value) -> list[float] | None:
    if not value:
        return None
    if isinstance(value, (tuple, list)):
        out = []
        for item in value:
            if isinstance(item, (tuple, list)):
                out.extend(float(v) for v in item if isinstance(v, (int, float)))
            elif isinstance(item, (int, float)):
                out.append(float(item))
        return out or None
    return None
