from __future__ import annotations

import math
from typing import Any


def build_project_vector_trace(raw: dict, label_positions: list[dict]) -> dict:
    pages = raw.get("pages") or []
    page = pages[0] if pages else {}
    page_width = float(page.get("width") or raw.get("pdf", {}).get("width") or 0) or 1.0
    page_height = float(page.get("height") or raw.get("pdf", {}).get("height") or 0) or 1.0

    clean = _clean_project_trace(raw, label_positions, page_width, page_height)
    if clean:
        return clean

    focus_points = _focus_points(raw, label_positions)
    focus_bounds = _bounds(focus_points) if focus_points else (0.0, 0.0, page_width, page_height)
    region = _expand_bounds(focus_bounds, 260, page_width, page_height)

    segments = []
    symbols = []
    seen: set[tuple[int, int, int, int, str]] = set()
    for drawing in raw.get("drawings") or []:
        segment = _segment_from_drawing(drawing, page_width, page_height, region)
        if segment:
            key = (
                round(segment["x1"]),
                round(segment["y1"]),
                round(segment["x2"]),
                round(segment["y2"]),
                segment["kind"],
            )
            if key not in seen:
                seen.add(key)
                segments.append(segment)
        symbol = _symbol_from_drawing(drawing, page_width, page_height, region)
        if symbol:
            symbols.append(symbol)
        if len(segments) >= 1600 and len(symbols) >= 400:
            break

    bounds_points = [
        point
        for segment in segments
        for point in ((segment["x1"], segment["y1"]), (segment["x2"], segment["y2"]))
    ]
    bounds_points.extend((symbol["x"], symbol["y"]) for symbol in symbols)
    bounds_points.extend(focus_points)
    bounds = _bounds(bounds_points) if bounds_points else region
    return {
        "mode": "focused_trace",
        "page_width": page_width,
        "page_height": page_height,
        "bounds": bounds,
        "segments": segments,
        "symbols": symbols,
        "labels": _trace_labels(label_positions, region),
    }


def _clean_project_trace(
    raw: dict,
    label_positions: list[dict],
    page_width: float,
    page_height: float,
) -> dict | None:
    segments: list[dict] = []
    bound_points: list[tuple[float, float]] = []
    seen: set[tuple[int, int, int, int, str]] = set()
    for drawing in raw.get("drawings") or []:
        segment = _clean_segment_from_drawing(drawing, page_width, page_height)
        if not segment:
            continue
        key = (
            round(segment["x1"]),
            round(segment["y1"]),
            round(segment["x2"]),
            round(segment["y2"]),
            segment["kind"],
        )
        if key in seen:
            continue
        seen.add(key)
        segments.append(segment)
        if segment["kind"] != "dark" or _segment_length(segment) > 20:
            bound_points.extend(
                [
                    (float(segment["x1"]), float(segment["y1"])),
                    (float(segment["x2"]), float(segment["y2"])),
                ]
            )
    if len(segments) < 30 or not bound_points:
        return None
    bounds = _clamped_bounds(bound_points, page_width, page_height)
    padded_bounds = _expand_bounds(bounds, 35, page_width, page_height)
    symbols = []
    for drawing in raw.get("drawings") or []:
        symbol = _symbol_from_drawing(drawing, page_width, page_height, padded_bounds)
        if symbol:
            symbols.append(symbol)
    labels = _trace_labels(label_positions, padded_bounds)
    return {
        "mode": "clean_project_trace",
        "page_width": page_width,
        "page_height": page_height,
        "bounds": padded_bounds,
        "segments": segments[:2600],
        "symbols": symbols[:600],
        "labels": labels,
    }


def _clean_segment_from_drawing(drawing: dict, page_width: float, page_height: float) -> dict[str, Any] | None:
    if drawing.get("type") != "line":
        return None
    points = drawing.get("points") or []
    if len(points) < 2:
        return None
    x1, y1 = float(points[0][0]), float(points[0][1])
    x2, y2 = float(points[1][0]), float(points[1][1])
    if not _inside_page(x1, y1, page_width, page_height) or not _inside_page(x2, y2, page_width, page_height):
        return None
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    if my > page_height * 0.82 or mx < 40 or mx > page_width - 20 or my < 25:
        return None
    length = math.hypot(x2 - x1, y2 - y1)
    if length < 8 or length > 520:
        return None
    kind = _clean_line_kind(drawing)
    if not kind:
        return None
    if kind == "blue" and length < 55:
        return None
    if kind == "dark":
        if length < 15 or length > 135:
            return None
        if mx < 230 and my < 230:
            return None
    width = float(drawing.get("width") or 0.7)
    return {
        "x1": round(x1, 3),
        "y1": round(y1, 3),
        "x2": round(x2, 3),
        "y2": round(y2, 3),
        "kind": kind,
        "width": round(max(0.35, min(width, 1.4)), 3),
    }


def _clean_line_kind(drawing: dict) -> str | None:
    color = drawing.get("stroke_color") or drawing.get("fill_color")
    if not color:
        return None
    r, g, b = [float(value) for value in color[:3]]
    avg = (r + g + b) / 3
    saturation = max(r, g, b) - min(r, g, b)
    if avg > 0.82:
        return None
    if r > 0.75 and g < 0.30 and b < 0.30:
        return "red"
    if b > 0.45 and r < 0.35:
        return "blue"
    if g > 0.40 and r < 0.45 and b < 0.45:
        return "green"
    if r > 0.34 and g < 0.28 and b < 0.12:
        return "brown"
    if r > 0.65 and b > 0.65 and g < 0.45:
        return "magenta"
    if saturation > 0.22 and avg < 0.75:
        return "color"
    if avg < 0.24:
        return "dark"
    return None


def _segment_length(segment: dict) -> float:
    return math.hypot(
        float(segment["x2"]) - float(segment["x1"]),
        float(segment["y2"]) - float(segment["y1"]),
    )


def _focus_points(raw: dict, label_positions: list[dict]) -> list[tuple[float, float]]:
    points = [
        (float(item.get("x") or 0), float(item.get("y") or 0))
        for item in label_positions
        if item.get("x") is not None and item.get("y") is not None
    ]
    for word in raw.get("words") or []:
        text = str(word.get("text") or "")
        if not text.startswith("P"):
            continue
        bbox = word.get("bbox") or {}
        points.append(
            (
                (float(bbox.get("x0") or 0) + float(bbox.get("x1") or 0)) / 2,
                (float(bbox.get("y0") or 0) + float(bbox.get("y1") or 0)) / 2,
            )
        )
    return points


def _segment_from_drawing(
    drawing: dict,
    page_width: float,
    page_height: float,
    region: tuple[float, float, float, float],
) -> dict[str, Any] | None:
    if drawing.get("type") != "line":
        return None
    points = drawing.get("points") or []
    if len(points) < 2:
        return None
    x1, y1 = float(points[0][0]), float(points[0][1])
    x2, y2 = float(points[1][0]), float(points[1][1])
    if not _inside_page(x1, y1, page_width, page_height) or not _inside_page(x2, y2, page_width, page_height):
        return None
    length = math.hypot(x2 - x1, y2 - y1)
    if length < 2 or length > 160:
        return None
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    kind = _line_kind(drawing)
    if kind not in {"blue", "red", "dark"}:
        return None
    if kind == "dark" and (length > 95 or not _inside_bounds(mx, my, region)):
        return None
    if kind in {"blue", "red"} and not _inside_bounds(mx, my, _expand_bounds(region, 160, page_width, page_height)):
        return None
    width = float(drawing.get("width") or 0.7)
    return {
        "x1": round(x1, 3),
        "y1": round(y1, 3),
        "x2": round(x2, 3),
        "y2": round(y2, 3),
        "kind": kind,
        "width": round(max(0.4, min(width, 2.2)), 3),
    }


def _symbol_from_drawing(
    drawing: dict,
    page_width: float,
    page_height: float,
    region: tuple[float, float, float, float],
) -> dict[str, Any] | None:
    if drawing.get("type") not in {"curve", "circle_like", "rect"}:
        return None
    bbox = drawing.get("bbox") or {}
    x0 = float(bbox.get("x0") or 0)
    y0 = float(bbox.get("y0") or 0)
    x1 = float(bbox.get("x1") or 0)
    y1 = float(bbox.get("y1") or 0)
    if not _inside_page(x0, y0, page_width, page_height) or not _inside_page(x1, y1, page_width, page_height):
        return None
    w = abs(x1 - x0)
    h = abs(y1 - y0)
    if w < 1.2 or h < 1.2 or max(w, h) > 28:
        return None
    x = (x0 + x1) / 2
    y = (y0 + y1) / 2
    if not _inside_bounds(x, y, _expand_bounds(region, 180, page_width, page_height)):
        return None
    kind = _line_kind(drawing)
    if kind not in {"dark", "red", "blue"}:
        return None
    return {
        "x": round(x, 3),
        "y": round(y, 3),
        "rx": round(max(w / 2, 1.0), 3),
        "ry": round(max(h / 2, 1.0), 3),
        "kind": kind,
    }


def _line_kind(drawing: dict) -> str:
    color = drawing.get("stroke_color")
    if color:
        r, g, b = [float(value) for value in color[:3]]
        if r > 0.75 and g < 0.35 and b < 0.35:
            return "red"
        if b > 0.55 and r < 0.25:
            return "blue"
        if (r + g + b) / 3 < 0.30:
            return "dark"
        return "other"
    fill = drawing.get("fill_color")
    if fill:
        r, g, b = [float(value) for value in fill[:3]]
        if (r + g + b) / 3 < 0.30:
            return "dark"
        return "other"
    return "dark"


def _trace_labels(label_positions: list[dict], region: tuple[float, float, float, float]) -> list[dict]:
    labels = []
    seen: set[str] = set()
    for item in label_positions:
        text = str(item.get("text") or "").strip()
        if not text or text in seen:
            continue
        x = float(item.get("x") or 0)
        y = float(item.get("y") or 0)
        if not _inside_bounds(x, y, region):
            continue
        labels.append({"text": text, "x": round(x, 3), "y": round(y, 3)})
        seen.add(text)
    return labels[:80]


def _inside_page(x: float, y: float, width: float, height: float) -> bool:
    return -5 <= x <= width + 5 and -5 <= y <= height + 5


def _inside_bounds(x: float, y: float, bounds: tuple[float, float, float, float]) -> bool:
    min_x, min_y, max_x, max_y = bounds
    return min_x <= x <= max_x and min_y <= y <= max_y


def _bounds(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    return (
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    )


def _clamped_bounds(
    points: list[tuple[float, float]],
    page_width: float,
    page_height: float,
) -> tuple[float, float, float, float]:
    clamped = [
        (
            min(max(point[0], 0.0), page_width),
            min(max(point[1], 0.0), page_height),
        )
        for point in points
    ]
    if len(clamped) < 40:
        return _bounds(clamped)
    xs = sorted(point[0] for point in clamped)
    ys = sorted(point[1] for point in clamped)
    return _quantile(xs, 0.02), _quantile(ys, 0.02), _quantile(xs, 0.98), _quantile(ys, 0.98)


def _quantile(values: list[float], fraction: float) -> float:
    index = max(0, min(len(values) - 1, int((len(values) - 1) * fraction)))
    return values[index]


def _expand_bounds(
    bounds: tuple[float, float, float, float],
    padding: float,
    page_width: float,
    page_height: float,
) -> tuple[float, float, float, float]:
    min_x, min_y, max_x, max_y = bounds
    return (
        max(0.0, min_x - padding),
        max(0.0, min_y - padding),
        min(page_width, max_x + padding),
        min(page_height, max_y + padding),
    )
