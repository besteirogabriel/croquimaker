from __future__ import annotations

import base64
import math
from html import escape
from pathlib import Path
from typing import Any

from croqui_engine.core.models import TechnicalPayload
from croqui_engine.output.contract import (
    main_equipment_label_from_payload,
    output_contract_from_payload,
    output_header_values,
    selected_equipment_code_from_payload,
)
from croqui_engine.rendering.final_croqui_renderer import VIABILITY_ROWS
from croqui_engine.symbols.official_symbol_assets import load_official_symbol_assets

PAGE_W = 841.68
PAGE_H = 595.20


def generate_svg_croqui(payload: TechnicalPayload, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_svg_document(payload), encoding="utf-8")
    return output_path


def generate_svg_croqui_pdf(payload: TechnicalPayload, output_path: Path) -> Path:
    import fitz

    svg_path = output_path.with_suffix(".svg")
    generate_svg_croqui(payload, svg_path)
    svg_bytes = svg_path.read_bytes()
    doc = fitz.open("svg", svg_bytes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(doc.convert_to_pdf())
    doc.close()
    return output_path


def _svg_document(payload: TechnicalPayload) -> str:
    body = [
        _defs(),
        '<rect x="0" y="0" width="841.68" height="595.2" fill="#fff"/>',
        '<rect x="20" y="42" width="801.68" height="500" fill="#fff" stroke="#111" stroke-width="0.8"/>',
        '<text x="420.84" y="28" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="8.5" font-weight="700">Croqui</text>',
        _rge_logo(),
        _header(payload),
        _network(payload),
        _viability(),
    ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{PAGE_W}pt" height="{PAGE_H}pt" '
        f'viewBox="0 0 {PAGE_W} {PAGE_H}" role="img">'
        + "".join(body)
        + "</svg>"
    )


def _defs() -> str:
    return """
    <defs>
      <style>
        .svg-note{fill:#000}
      </style>
      <g id="pole"><circle cx="0" cy="0" r="3" fill="#fff" stroke="#111" stroke-width="0.7"/><circle cx="0" cy="0" r="1" fill="none" stroke="#111" stroke-width="0.45"/></g>
    </defs>
    """


def _rge_logo() -> str:
    return """
    <g transform="translate(24 74)">
      <text x="0" y="0" font-family="Arial,Helvetica,sans-serif" font-size="23" font-style="italic" font-weight="700">RGE</text>
      <text x="43" y="-5" font-family="Arial,Helvetica,sans-serif" font-size="4.5" font-weight="700">Rio GrandeEnergia</text>
      <line x1="86" y1="-8" x2="248" y2="-8" stroke="#111" stroke-width="0.6"/>
      <circle cx="248" cy="-8" r="0.9" fill="#111"/>
    </g>
    """


def _header(payload: TechnicalPayload) -> str:
    x, y, w, h = 20, 86, 801.68, 24
    values = output_header_values(payload)
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#fff" stroke="#111" stroke-width="0.4"/>',
        f'<line x1="{x}" y1="{y + 12}" x2="{x + w}" y2="{y + 12}" stroke="#111" stroke-width="0.4"/>',
    ]
    for px in (x + 120, x + 270, x + 385, x + 585, x + 645):
        parts.append(f'<line x1="{px}" y1="{y}" x2="{px}" y2="{y + h}" stroke="#111" stroke-width="0.4"/>')
    labels = [
        ("Departamento:", x + 2, y + 8),
        ("Município:", x + 272, y + 8),
        ("Equipamento :", x + 588, y + 8),
        ("Data do Levantamento:", x + 2, y + 20),
        ("Levantamento de campo realizado por:", x + 272, y + 20),
    ]
    for text, tx, ty in labels:
        parts.append(
            f'<text x="{tx}" y="{ty}" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="4.8" font-weight="700">{escape(text)}</text>'
        )
    centered = [
        (values["department"], x + 195, y + 8),
        (values["municipality"], x + 485, y + 8),
        (values["equipment"], x + 730, y + 8),
        (values["survey_date"], x + 195, y + 20),
        (values["surveyor"], x + 700, y + 20),
    ]
    for text, tx, ty in centered:
        parts.append(
            f'<text x="{tx}" y="{ty}" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="4.8">{escape(text)}</text>'
        )
    return "".join(parts)


def _network(payload: TechnicalPayload) -> str:
    frame = (35.0, 122.0, 770.0, 320.0)
    layout = payload.meta.get("schematic_layout") or {}
    if layout.get("source") == "SchematicLayoutEngine":
        return _schematic_layout_network(layout, frame)
    return _payload_network(payload, frame)


def _schematic_layout_network(layout: dict, frame: tuple[float, float, float, float]) -> str:
    x, y, w, h = frame
    nodes = layout.get("nodes") or []
    edges = layout.get("edges") or []
    labels = layout.get("labels") or []
    work_zones = layout.get("work_zones") or []
    if not nodes:
        return (
            f'<text x="{x + w / 2}" y="{y + h / 2}" text-anchor="middle" '
            f'font-family="Arial,Helvetica,sans-serif" font-size="4.8" fill="#666">'
            "Topologia esquematica nao identificada com seguranca. Revise o payload antes da emissao."
            "</text>"
        )

    project, size_project = _schematic_projectors(layout, frame)
    node_by_id = {str(node.get("id") or ""): node for node in nodes}
    parts = ['<g clip-path="url(#clip-network)">', _network_clip(x, y, w, h)]
    for edge in edges:
        points = edge.get("points") or []
        if len(points) < 2:
            start = node_by_id.get(str(edge.get("from_node") or ""))
            end = node_by_id.get(str(edge.get("to_node") or ""))
            if not start or not end:
                continue
            points = [(start.get("x"), start.get("y")), (end.get("x"), end.get("y"))]
        mapped = [_format_point(project(float(px), float(py))) for px, py in points]
        dash = ' stroke-dasharray="4 3"' if str(edge.get("type") or "").endswith("INFERIDA") else ""
        width = "0.78" if edge.get("type") != "EQUIPAMENTO" else "0.62"
        parts.append(
            f'<polyline points="{" ".join(mapped)}" stroke="#303438" stroke-width="{width}" '
            f'fill="none" stroke-linecap="round" stroke-linejoin="round"{dash}/>'
        )

    for node in nodes:
        nx, ny = project(float(node.get("x") or 0), float(node.get("y") or 0))
        parts.append(_schematic_node_symbol(node, nx, ny))

    for label in labels:
        lx, ly = project(float(label.get("x") or 0), float(label.get("y") or 0))
        text = escape(str(label.get("text") or ""))
        focus = label.get("role") == "focus_label"
        font_size = "6.8" if focus else "6.0"
        weight = "700" if focus else "400"
        parts.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="{font_size}" font-weight="{weight}">{text}</text>'
        )

    parts.append("</g>")
    for zone in work_zones:
        zx, zy = project(float(zone.get("x") or 0), float(zone.get("y") or 0))
        zw, zh = size_project(float(zone.get("width") or 0), float(zone.get("height") or 0))
        angle = float(zone.get("angle") or -12)
        parts.append(_dashed_rotated_rect(zx, zy, zw, zh, angle))
        parts.append(_red_marks(zx, zy))
    return "".join(parts)


def _schematic_projectors(
    layout: dict,
    frame: tuple[float, float, float, float],
) -> tuple[Any, Any]:
    x, y, w, h = frame
    canvas = layout.get("canvas") or {}
    canvas_w = float(canvas.get("width") or 1000.0)
    canvas_h = float(canvas.get("height") or 420.0)

    def project(px: float, py: float) -> tuple[float, float]:
        return x + (px / canvas_w) * w, y + (py / canvas_h) * h

    def size_project(width: float, height: float) -> tuple[float, float]:
        return (width / canvas_w) * w, (height / canvas_h) * h

    return project, size_project


def _format_point(point: tuple[float, float]) -> str:
    return f"{point[0]:.2f},{point[1]:.2f}"


def _schematic_node_symbol(node: dict, x: float, y: float) -> str:
    node_type = str(node.get("type") or "").upper()
    code = escape(str(node.get("code") or ""))
    focus = bool(node.get("is_focus"))
    if node_type in {"POSTE", "EQUIPAMENTO_REFERENCIA"}:
        symbol = f'<use href="#pole" x="{x:.2f}" y="{y:.2f}"/>'
    elif node_type in {"TR", "TRANSFORMADOR"}:
        symbol = (
            f'<g transform="translate({x:.2f} {y:.2f})">'
            '<rect x="-8" y="-7" width="16" height="14" fill="#fff" stroke="#111" stroke-width="0.85"/>'
            '<circle cx="-3.2" cy="0" r="3.2" fill="none" stroke="#111" stroke-width="0.6"/>'
            '<circle cx="3.2" cy="0" r="3.2" fill="none" stroke="#111" stroke-width="0.6"/>'
            "</g>"
        )
    elif node_type in {"FU", "FC", "CF", "RL", "SC"}:
        label = "FC" if node_type == "CF" else node_type[:2]
        symbol = (
            f'<g transform="translate({x:.2f} {y:.2f})">'
            '<line x1="-12" y1="0" x2="12" y2="0" stroke="#111" stroke-width="0.85"/>'
            '<line x1="-2" y1="0" x2="7" y2="-6" stroke="#111" stroke-width="0.75"/>'
            '<circle cx="-12" cy="0" r="1.7" fill="#111"/>'
            '<circle cx="12" cy="0" r="1.7" fill="#111"/>'
            f'<text x="0" y="12" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="4.7">{escape(label)}</text>'
            "</g>"
        )
    else:
        symbol = (
            f'<rect x="{x - 5:.2f}" y="{y - 5:.2f}" width="10" height="10" '
            'fill="#fff" stroke="#111" stroke-width="0.75"/>'
        )
    if not focus:
        return symbol
    focus_ring = (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="13.5" fill="none" '
        'stroke="#e60000" stroke-width="0.8" stroke-dasharray="3 2"/>'
    )
    code_label = (
        f'<text x="{x:.2f}" y="{y - 16:.2f}" text-anchor="middle" '
        'font-family="Arial,Helvetica,sans-serif" font-size="5.6" font-weight="700" fill="#e60000">'
        f'{code}</text>'
    ) if code else ""
    return focus_ring + symbol + code_label


def _schematic_network(trace: dict, payload: TechnicalPayload, frame: tuple[float, float, float, float]) -> str:
    graph = _schematic_graph(trace, payload)
    if not graph["edges"]:
        return _trace_network(trace, payload, frame)
    x, y, w, h = frame
    points = [node["point"] for node in graph["nodes"].values()]
    points.extend((float(label["x"]), float(label["y"])) for label in graph["labels"])
    min_x, min_y, max_x, max_y = _point_bounds(points)
    pad = 18.0
    if max_x - min_x < 1:
        max_x += 1
    if max_y - min_y < 1:
        max_y += 1
    scale_x = (w - pad * 2) / (max_x - min_x)
    scale_y = (h - pad * 2) / (max_y - min_y)
    used_w = (max_x - min_x) * scale_x
    used_h = (max_y - min_y) * scale_y
    x0 = x + (w - used_w) / 2
    y0 = y + (h - used_h) / 2

    def project(px: float, py: float) -> tuple[float, float]:
        return x0 + (px - min_x) * scale_x, y0 + (py - min_y) * scale_y

    parts = ['<g clip-path="url(#clip-network)">', _network_clip(x, y, w, h)]
    for edge in graph["edges"]:
        a = graph["nodes"][edge["a"]]["point"]
        b = graph["nodes"][edge["b"]]["point"]
        ax, ay = project(a[0], a[1])
        bx, by = project(b[0], b[1])
        dash = ' stroke-dasharray="3 2"' if edge["network"] == "primary" else ""
        width = 0.62 if edge["network"] == "primary" else 0.72
        parts.append(
            f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{bx:.2f}" y2="{by:.2f}" '
            f'stroke="#303438" stroke-width="{width}" fill="none"{dash}/>'
        )
    for node in graph["nodes"].values():
        if node["degree"] <= 1 and not node["label"]:
            continue
        nx, ny = project(node["point"][0], node["point"][1])
        parts.append(f'<use href="#pole" x="{nx:.2f}" y="{ny:.2f}"/>')
    for label in graph["labels"]:
        lx, ly = project(float(label["x"]), float(label["y"]))
        parts.append(
            f'<text x="{lx + 3:.2f}" y="{ly - 2:.2f}" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="3.9">{escape(str(label["text"]))}</text>'
        )
    parts.append(_equipment_symbols(trace, payload, project))
    parts.append("</g>")
    parts.append(_trace_work_area(trace, payload, project))
    return "".join(parts)


def _schematic_graph(trace: dict, payload: TechnicalPayload) -> dict:
    segments = [
        segment
        for segment in trace.get("segments") or []
        if segment.get("kind") in {"blue", "green", "color"} and _segment_length(segment) >= 34
    ]
    nodes: dict[int, dict] = {}
    edges: list[dict] = []

    def snap(point: tuple[float, float]) -> int:
        for node_id, node in nodes.items():
            if math.hypot(point[0] - node["point"][0], point[1] - node["point"][1]) <= 18:
                count = node["count"] + 1
                node["point"] = (
                    (node["point"][0] * node["count"] + point[0]) / count,
                    (node["point"][1] * node["count"] + point[1]) / count,
                )
                node["count"] = count
                return node_id
        node_id = len(nodes)
        nodes[node_id] = {"point": point, "count": 1, "degree": 0, "label": False}
        return node_id

    for segment in segments:
        a = snap((float(segment["x1"]), float(segment["y1"])))
        b = snap((float(segment["x2"]), float(segment["y2"])))
        if a == b:
            continue
        edges.append(
            {
                "a": a,
                "b": b,
                "length": _distance(nodes[a]["point"], nodes[b]["point"]),
                "network": _schematic_network_type(segment),
            }
        )
    edges = _prune_schematic_edges(nodes, edges, payload, trace)
    _recompute_degrees(nodes, edges)
    kept_nodes = {edge["a"] for edge in edges} | {edge["b"] for edge in edges}
    labels = _schematic_labels(trace, payload, nodes, kept_nodes)
    for label in labels:
        nearest = _nearest_node((float(label["x"]), float(label["y"])), nodes, kept_nodes)
        if nearest is not None:
            nodes[nearest]["label"] = True
    nodes = {node_id: node for node_id, node in nodes.items() if node_id in kept_nodes}
    return {"nodes": nodes, "edges": edges, "labels": labels}


def _schematic_network_type(segment: dict) -> str:
    if segment.get("kind") in {"green", "color", "dark"}:
        return "primary"
    return "secondary"


def _prune_schematic_edges(
    nodes: dict[int, dict],
    edges: list[dict],
    payload: TechnicalPayload,
    trace: dict,
) -> list[dict]:
    protected_points = [
        (float(label["x"]), float(label["y"]))
        for label in trace.get("labels") or []
        if _label_is_relevant(str(label.get("text") or ""), payload)
    ]
    selected = list(edges)
    for _ in range(5):
        degree: dict[int, int] = {}
        for edge in selected:
            degree[edge["a"]] = degree.get(edge["a"], 0) + 1
            degree[edge["b"]] = degree.get(edge["b"], 0) + 1
        next_edges = []
        changed = False
        for edge in selected:
            a_leaf = degree.get(edge["a"], 0) <= 1
            b_leaf = degree.get(edge["b"], 0) <= 1
            keep = True
            if (a_leaf or b_leaf) and edge["length"] < 95:
                a = nodes[edge["a"]]["point"]
                b = nodes[edge["b"]]["point"]
                keep = _edge_near_any_label(a, b, protected_points)
            if keep:
                next_edges.append(edge)
            else:
                changed = True
        selected = next_edges
        if not changed:
            break
    components = _edge_components(selected)
    if not components:
        return selected
    ranked = sorted(
        components,
        key=lambda group: sum(selected[index]["length"] for index in group),
        reverse=True,
    )
    keep_indices = set(ranked[0])
    for group in ranked[1:]:
        length = sum(selected[index]["length"] for index in group)
        if length >= 220:
            keep_indices.update(group)
    selected = [edge for index, edge in enumerate(selected) if index in keep_indices]
    return _maximum_spanning_forest(selected)


def _maximum_spanning_forest(edges: list[dict]) -> list[dict]:
    parent: dict[int, int] = {}

    def find(node: int) -> int:
        parent.setdefault(node, node)
        if parent[node] != node:
            parent[node] = find(parent[node])
        return parent[node]

    def union(a: int, b: int) -> bool:
        root_a = find(a)
        root_b = find(b)
        if root_a == root_b:
            return False
        parent[root_b] = root_a
        return True

    output = []
    for edge in sorted(edges, key=lambda item: item["length"], reverse=True):
        if union(edge["a"], edge["b"]):
            output.append(edge)
    return output


def _schematic_labels(trace: dict, payload: TechnicalPayload, nodes: dict[int, dict], kept_nodes: set[int]) -> list[dict]:
    labels = []
    seen: set[str] = set()
    equipment_codes = {equipment.code for equipment in payload.active_equipment()}
    source_labels = [
        *(trace.get("labels") or []),
        *(payload.meta.get("project_numeric_label_positions") or []),
    ]
    for label in source_labels:
        text = str(label.get("text") or "")
        if text in seen:
            continue
        if text not in equipment_codes and _nearest_node_distance((float(label["x"]), float(label["y"])), nodes, kept_nodes) > 160:
            continue
        labels.append(label)
        seen.add(text)
    return labels[:45]


def _label_is_relevant(text: str, payload: TechnicalPayload) -> bool:
    return text in {equipment.code for equipment in payload.active_equipment()}


def _edge_near_any_label(
    a: tuple[float, float],
    b: tuple[float, float],
    labels: list[tuple[float, float]],
) -> bool:
    return any(_point_segment_distance(label, a, b) <= 60 for label in labels)


def _edge_components(edges: list[dict]) -> list[set[int]]:
    by_node: dict[int, list[int]] = {}
    for index, edge in enumerate(edges):
        by_node.setdefault(edge["a"], []).append(index)
        by_node.setdefault(edge["b"], []).append(index)
    components = []
    seen: set[int] = set()
    for index in range(len(edges)):
        if index in seen:
            continue
        stack = [index]
        group: set[int] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            group.add(current)
            edge = edges[current]
            for node_id in (edge["a"], edge["b"]):
                stack.extend(item for item in by_node.get(node_id, []) if item not in seen)
        components.append(group)
    return components


def _recompute_degrees(nodes: dict[int, dict], edges: list[dict]) -> None:
    for node in nodes.values():
        node["degree"] = 0
    for edge in edges:
        nodes[edge["a"]]["degree"] += 1
        nodes[edge["b"]]["degree"] += 1


def _nearest_node(
    point: tuple[float, float],
    nodes: dict[int, dict],
    kept_nodes: set[int],
) -> int | None:
    if not kept_nodes:
        return None
    return min(kept_nodes, key=lambda node_id: _distance(point, nodes[node_id]["point"]))


def _nearest_node_distance(point: tuple[float, float], nodes: dict[int, dict], kept_nodes: set[int]) -> float:
    nearest = _nearest_node(point, nodes, kept_nodes)
    return _distance(point, nodes[nearest]["point"]) if nearest is not None else 999999.0


def _point_segment_distance(
    point: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    ax, ay = a
    bx, by = b
    px, py = point
    length_sq = (bx - ax) ** 2 + (by - ay) ** 2
    if length_sq <= 0:
        return _distance(point, a)
    t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / length_sq))
    projected = (ax + t * (bx - ax), ay + t * (by - ay))
    return _distance(point, projected)


def _point_bounds(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    return (
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    )


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _trace_network(trace: dict, payload: TechnicalPayload, frame: tuple[float, float, float, float]) -> str:
    x, y, w, h = frame
    trace = _focused_trace(trace, payload)
    min_x, min_y, max_x, max_y = [float(value) for value in trace.get("bounds") or (0, 0, 1, 1)]
    if max_x - min_x < 1:
        max_x += 1
    if max_y - min_y < 1:
        max_y += 1
    pad = 20.0
    scale = min((w - pad * 2) / (max_x - min_x), (h - pad * 2) / (max_y - min_y))
    used_w = (max_x - min_x) * scale
    used_h = (max_y - min_y) * scale
    x0 = x + (w - used_w) / 2
    y0 = y + (h - used_h) / 2

    def project(px: float, py: float) -> tuple[float, float]:
        return x0 + (px - min_x) * scale, y0 + (py - min_y) * scale

    segments = list(trace.get("segments") or [])
    parts = ['<g clip-path="url(#clip-network)">', _network_clip(x, y, w, h)]
    for kind in ("dark", "green", "color", "blue", "brown", "magenta", "red"):
        for segment in segments:
            if segment.get("kind") != kind:
                continue
            if trace.get("mode") != "clean_project_trace" and kind == "red" and _segment_length(segment) > 45:
                continue
            sx1, sy1 = project(float(segment["x1"]), float(segment["y1"]))
            sx2, sy2 = project(float(segment["x2"]), float(segment["y2"]))
            stroke = _trace_stroke(kind)
            dash = _trace_dash(kind, trace)
            width = _trace_width(kind, segment, trace)
            parts.append(
                f'<line x1="{sx1:.2f}" y1="{sy1:.2f}" x2="{sx2:.2f}" y2="{sy2:.2f}" '
                f'stroke="{stroke}" stroke-width="{width}" fill="none"{dash}/>'
            )
    for symbol in trace.get("symbols") or []:
        sx, sy = project(float(symbol["x"]), float(symbol["y"]))
        rx = max(float(symbol.get("rx") or 1.0) * scale, 1.6)
        ry = max(float(symbol.get("ry") or 1.0) * scale, 1.6)
        stroke = "#e60000" if symbol.get("kind") == "red" else "#2f3437"
        parts.append(
            f'<ellipse cx="{sx:.2f}" cy="{sy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" '
            f'fill="#fff" stroke="{stroke}" stroke-width="0.75"/>'
        )
    for label in trace.get("labels") or []:
        lx, ly = project(float(label["x"]), float(label["y"]))
        parts.append(
            f'<text x="{lx + 2:.2f}" y="{ly - 2:.2f}" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="4.2">{escape(str(label["text"]))}</text>'
        )
    parts.append(_equipment_symbols(trace, payload, project))
    parts.append("</g>")
    parts.append(_trace_work_area(trace, payload, project))
    return "".join(parts)


def _equipment_symbols(trace: dict, payload: TechnicalPayload, project: Any) -> str:
    equipment_by_code = {equipment.code: equipment for equipment in payload.active_equipment()}
    assets = _official_asset_data()
    if not assets:
        return ""
    parts = []
    for label in trace.get("labels") or []:
        equipment = equipment_by_code.get(str(label.get("text") or ""))
        if not equipment:
            continue
        asset_id = _asset_id_for_equipment(equipment)
        if not asset_id or asset_id not in assets:
            continue
        x, y = project(float(label["x"]), float(label["y"]))
        width, height = _asset_size(asset_id)
        parts.append(_asset_image(assets[asset_id]["href"], x, y - 8, width, height))
    return "".join(parts)


def _trace_stroke(kind: str) -> str:
    return {
        "red": "#e60000",
        "blue": "#1c33ff",
        "brown": "#d07a00",
        "magenta": "#ef28d8",
        "green": "#303438",
        "color": "#303438",
        "dark": "#303438",
    }.get(kind, "#303438")


def _trace_dash(kind: str, trace: dict) -> str:
    if trace.get("mode") == "clean_project_trace":
        return ' stroke-dasharray="3 2"' if kind in {"green", "color"} else ""
    return ' stroke-dasharray="4 3"' if kind in {"blue", "red"} else ""


def _trace_width(kind: str, segment: dict, trace: dict) -> float:
    if trace.get("mode") == "clean_project_trace":
        base = float(segment.get("width") or 0.6)
        if kind == "red":
            return max(0.75, min(base, 1.1))
        if kind in {"blue", "brown", "magenta"}:
            return max(0.62, min(base, 0.9))
        return max(0.45, min(base, 0.75))
    return 1.0 if kind == "red" else 0.8


def _official_asset_data() -> dict[str, dict]:
    output = {}
    for asset_id, item in load_official_symbol_assets().items():
        raw = Path(item["path"]).read_bytes()
        href = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
        output[asset_id] = {**item, "href": href}
    return output


def _asset_id_for_equipment(equipment: Any) -> str | None:
    eq_type = str(getattr(equipment, "type", "") or "").upper()
    status = str(getattr(equipment, "status", "") or "").lower()
    raw_text = str(getattr(equipment, "raw_text", "") or "").lower()
    context = f"{status} {raw_text}"
    if eq_type == "TRANSFORMADOR":
        return "TRANSFORMADOR_RGE"
    if eq_type == "CHAVE_FUSIVEL":
        if "relig" in context or "repet" in context:
            return "CHAVE_FUSIVEL_RELIGADORA"
        if "abrir" in context or "abertura" in context:
            return "CHAVE_FUSIVEL_COM_ABERTURA"
        return "CHAVE_FUSIVEL_SEM_ABERTURA"
    if eq_type == "CHAVE_COMANDO":
        if "abrir" in context or "abertura" in context:
            return "CHAVE_FACA_COM_ABERTURA"
        return "CHAVE_FACA_SEM_ABERTURA"
    if eq_type == "RELIGADOR":
        return "RELIGADOR"
    if eq_type == "SECCIONALIZADORA":
        return "SECCIONALIZADORA"
    if eq_type == "REGULADOR":
        return "REGULADOR_TENSAO"
    return None


def _asset_size(asset_id: str) -> tuple[float, float]:
    if asset_id.startswith("TRANSFORMADOR"):
        return 16.0, 16.0
    if asset_id in {"RELIGADOR", "SECCIONALIZADORA", "REGULADOR_TENSAO"}:
        return 19.0, 16.0
    if asset_id.startswith("CHAVE"):
        return 28.0, 13.0
    return 22.0, 14.0


def _asset_image(href: str, cx: float, cy: float, width: float, height: float) -> str:
    return (
        f'<image href="{href}" x="{cx - width / 2:.2f}" y="{cy - height / 2:.2f}" '
        f'width="{width:.2f}" height="{height:.2f}" preserveAspectRatio="xMidYMid meet"/>'
    )


def _focused_trace(trace: dict, payload: TechnicalPayload) -> dict:
    contract = output_contract_from_payload(payload)
    if contract and contract.focus_region:
        focused = _trace_for_contract_region(trace, contract.focus_region)
        if focused.get("segments") or focused.get("labels"):
            return focused
    if trace.get("mode") == "clean_project_trace":
        return trace
    segments = list(trace.get("segments") or [])
    symbols = list(trace.get("symbols") or [])
    labels = list(trace.get("labels") or [])
    red_points = [
        point
        for segment in segments
        if segment.get("kind") == "red"
        for point in ((float(segment["x1"]), float(segment["y1"])), (float(segment["x2"]), float(segment["y2"])))
    ]
    main_code = _main_equipment_code(payload)
    main_points = [
        (float(label["x"]), float(label["y"]))
        for label in labels
        if main_code and label.get("text") == main_code
    ]
    focus_points = red_points or main_points
    if not focus_points:
        return trace
    cx = sum(point[0] for point in focus_points) / len(focus_points)
    cy = sum(point[1] for point in focus_points) / len(focus_points)
    radius = 520
    selected_segments = []
    for segment in segments:
        mx = (float(segment["x1"]) + float(segment["x2"])) / 2
        my = (float(segment["y1"]) + float(segment["y2"])) / 2
        distance = ((mx - cx) ** 2 + (my - cy) ** 2) ** 0.5
        if distance <= radius or segment.get("kind") == "red":
            selected_segments.append(segment)
    if len(selected_segments) < 20:
        return trace
    selected_labels = []
    for label in labels:
        lx, ly = float(label["x"]), float(label["y"])
        if ((lx - cx) ** 2 + (ly - cy) ** 2) ** 0.5 <= radius + 80:
            selected_labels.append(label)
    selected_symbols = []
    for symbol in symbols:
        sx, sy = float(symbol["x"]), float(symbol["y"])
        if ((sx - cx) ** 2 + (sy - cy) ** 2) ** 0.5 <= radius + 80:
            selected_symbols.append(symbol)
    points = [
        point
        for segment in selected_segments
        for point in ((float(segment["x1"]), float(segment["y1"])), (float(segment["x2"]), float(segment["y2"])))
    ]
    points.extend((float(label["x"]), float(label["y"])) for label in selected_labels)
    points.extend((float(symbol["x"]), float(symbol["y"])) for symbol in selected_symbols)
    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_x = max(point[0] for point in points)
    max_y = max(point[1] for point in points)
    return {
        **trace,
        "segments": selected_segments,
        "symbols": selected_symbols,
        "labels": selected_labels,
        "bounds": (min_x, min_y, max_x, max_y),
    }


def _trace_for_contract_region(trace: dict, region: dict[str, float]) -> dict:
    padding = 80.0
    expanded = {
        "x0": float(region["x0"]) - padding,
        "y0": float(region["y0"]) - padding,
        "x1": float(region["x1"]) + padding,
        "y1": float(region["y1"]) + padding,
    }
    selected_segments = []
    for segment in trace.get("segments") or []:
        mx = (float(segment["x1"]) + float(segment["x2"])) / 2
        my = (float(segment["y1"]) + float(segment["y2"])) / 2
        if _inside_region(mx, my, expanded):
            selected_segments.append(segment)
    selected_symbols = [
        symbol
        for symbol in trace.get("symbols") or []
        if _inside_region(float(symbol.get("x") or 0), float(symbol.get("y") or 0), expanded)
    ]
    selected_labels = [
        label
        for label in trace.get("labels") or []
        if _inside_region(float(label.get("x") or 0), float(label.get("y") or 0), expanded)
    ]
    points = [
        point
        for segment in selected_segments
        for point in ((float(segment["x1"]), float(segment["y1"])), (float(segment["x2"]), float(segment["y2"])))
    ]
    points.extend((float(label["x"]), float(label["y"])) for label in selected_labels)
    points.extend((float(symbol["x"]), float(symbol["y"])) for symbol in selected_symbols)
    if not points:
        return {**trace, "segments": [], "symbols": [], "labels": [], "bounds": tuple(region.values())}
    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_x = max(point[0] for point in points)
    max_y = max(point[1] for point in points)
    return {
        **trace,
        "mode": f"{trace.get('mode', 'trace')}_contract_focus",
        "segments": selected_segments,
        "symbols": selected_symbols,
        "labels": selected_labels,
        "bounds": (min_x, min_y, max_x, max_y),
    }


def _inside_region(x: float, y: float, region: dict[str, float]) -> bool:
    return region["x0"] <= x <= region["x1"] and region["y0"] <= y <= region["y1"]


def _network_clip(x: float, y: float, w: float, h: float) -> str:
    return (
        "<clipPath id=\"clip-network\">"
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}"/>'
        "</clipPath>"
    )


def _trace_work_area(trace: dict, payload: TechnicalPayload, project: Any) -> str:
    contract = output_contract_from_payload(payload)
    if contract and contract.primary_focus_bbox:
        bbox = contract.primary_focus_bbox
        cx = (float(bbox["x0"]) + float(bbox["x1"])) / 2
        cy = (float(bbox["y0"]) + float(bbox["y1"])) / 2
        mx, my = project(cx, cy)
        return _dashed_rotated_rect(mx + 28, my - 8, 92, 46, -14) + _red_marks(mx + 28, my - 8)
    if contract and contract.focus_region:
        region = contract.focus_region
        cx = (float(region["x0"]) + float(region["x1"])) / 2
        cy = (float(region["y0"]) + float(region["y1"])) / 2
        mx, my = project(cx, cy)
        return _dashed_rotated_rect(mx, my, 104, 54, -16) + _red_marks(mx, my)

    main_code = _main_equipment_code(payload)
    work_points = []
    if trace.get("mode") == "clean_project_trace" and main_code:
        for label in trace.get("labels") or []:
            if label.get("text") == main_code:
                mx, my = project(float(label["x"]), float(label["y"]))
                return _dashed_rotated_rect(mx + 42, my - 8, 105, 44, -12) + _red_marks(mx + 42, my - 8)
    red_points = [
        point
        for segment in trace.get("segments") or []
        if segment.get("kind") == "red" and _segment_length(segment) <= 45
        for point in ((float(segment["x1"]), float(segment["y1"])), (float(segment["x2"]), float(segment["y2"])))
    ]
    if trace.get("mode") == "clean_project_trace":
        work_points = _dominant_points(red_points)
    if main_code and not work_points:
        for label in trace.get("labels") or []:
            if label.get("text") == main_code:
                work_points.append((float(label["x"]), float(label["y"])))
                break
    if not work_points:
        work_points = _dominant_points(red_points)
    if not work_points:
        return ""
    mapped = [project(px, py) for px, py in work_points]
    min_x = min(px for px, _ in mapped) - 34
    max_x = max(px for px, _ in mapped) + 34
    min_y = min(py for _, py in mapped) - 28
    max_y = max(py for _, py in mapped) + 28
    cx, cy = (min_x + max_x) / 2, (min_y + max_y) / 2
    w, h = max(max_x - min_x, 75), max(max_y - min_y, 52)
    return _dashed_rotated_rect(cx, cy, w, h, -18) + _red_marks(cx, cy)


def _dominant_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not points:
        return []
    clusters: list[list[tuple[float, float]]] = []
    radius = 150.0
    for point in points:
        for cluster in clusters:
            cx = sum(item[0] for item in cluster) / len(cluster)
            cy = sum(item[1] for item in cluster) / len(cluster)
            if math.hypot(point[0] - cx, point[1] - cy) <= radius:
                cluster.append(point)
                break
        else:
            clusters.append([point])
    clusters.sort(key=lambda items: (len(items), -sum(item[1] for item in items) / len(items)), reverse=True)
    return clusters[0]


def _dashed_rotated_rect(cx: float, cy: float, width: float, height: float, angle: float) -> str:
    theta = math.radians(angle)
    ct, st = math.cos(theta), math.sin(theta)
    raw = [
        (-width / 2, -height / 2),
        (width / 2, -height / 2),
        (width / 2, height / 2),
        (-width / 2, height / 2),
    ]
    points = [(cx + x * ct - y * st, cy + x * st + y * ct) for x, y in raw]
    return "".join(_svg_dashed_segment(a, b) for a, b in zip(points, [*points[1:], points[0]], strict=False))


def _svg_dashed_segment(a: tuple[float, float], b: tuple[float, float]) -> str:
    ax, ay = a
    bx, by = b
    length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
    if length <= 0:
        return ""
    vx, vy = (bx - ax) / length, (by - ay) / length
    parts = []
    cursor = 0.0
    dash, gap = 3.0, 3.8
    while cursor < length:
        end = min(cursor + dash, length)
        x1, y1 = ax + vx * cursor, ay + vy * cursor
        x2, y2 = ax + vx * end, ay + vy * end
        parts.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            'stroke="#e60000" stroke-width="1" fill="none"/>'
        )
        cursor += dash + gap
    return "".join(parts)


def _segment_length(segment: dict) -> float:
    return (
        (float(segment["x2"]) - float(segment["x1"])) ** 2
        + (float(segment["y2"]) - float(segment["y1"])) ** 2
    ) ** 0.5


def _payload_network(payload: TechnicalPayload, frame: tuple[float, float, float, float]) -> str:
    x, y, w, h = frame
    points = [
        (float(node.x), float(node.y))
        for node in payload.active_nodes()
        if node.x is not None and node.y is not None
    ]
    if not points:
        return (
            f'<text x="{x + w / 2}" y="{y + h / 2}" text-anchor="middle" '
            f'font-family="Arial,Helvetica,sans-serif" font-size="4.8" fill="#666">'
            "Topologia nao identificada com seguranca. Revise o payload antes da emissao."
            "</text>"
        )
    min_x, min_y = min(px for px, _ in points), min(py for _, py in points)
    max_x, max_y = max(px for px, _ in points), max(py for _, py in points)
    if max_x - min_x < 1:
        max_x += 1
    if max_y - min_y < 1:
        max_y += 1
    scale = min(w / (max_x - min_x), h / (max_y - min_y)) * 0.82
    x0 = x + (w - (max_x - min_x) * scale) / 2
    y0 = y + (h - (max_y - min_y) * scale) / 2

    def project(point: tuple[float, float]) -> tuple[float, float]:
        return x0 + (point[0] - min_x) * scale, y0 + (point[1] - min_y) * scale

    node_positions = {
        node.id: project((float(node.x), float(node.y)))
        for node in payload.active_nodes()
        if node.x is not None and node.y is not None
    }
    parts = []
    for span in payload.active_spans():
        a = node_positions.get(span.from_node)
        b = node_positions.get(span.to_node)
        if not a or not b:
            continue
        parts.append(
            f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" '
            'stroke="#555" stroke-width="0.7" stroke-dasharray="4 3"/>'
        )
    for node_id, (nx, ny) in node_positions.items():
        parts.append(f'<use href="#pole" x="{nx:.2f}" y="{ny:.2f}"/>')
        parts.append(
            f'<text x="{nx - 5:.2f}" y="{ny + 13:.2f}" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="4.2">{escape(node_id)}</text>'
        )
    return "".join(parts)


def _red_marks(cx: float, cy: float) -> str:
    parts = []
    for dx, dy, angle in [(-18, 8, -28), (10, -4, -28), (30, 14, -28)]:
        x, y = cx + dx, cy + dy
        parts.append(
            f'<g transform="translate({x:.2f} {y:.2f}) rotate({angle})">'
            '<line x1="-12" y1="0" x2="12" y2="0" stroke="#e60000" stroke-width="0.8"/>'
            '<line x1="4" y1="-4" x2="12" y2="0" stroke="#e60000" stroke-width="0.8"/>'
            '<line x1="4" y1="4" x2="12" y2="0" stroke="#e60000" stroke-width="0.8"/>'
            "</g>"
        )
    return "".join(parts)


def _viability() -> str:
    x, y, w = 20, 454, 801.68
    row_h = 8.1
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{row_h * 11:.2f}" fill="#fff" stroke="#111" stroke-width="0.35"/>',
        f'<rect x="{x}" y="{y}" width="{w}" height="{row_h}" fill="#fff36d"/>',
        f'<text x="{x + w * 0.36:.2f}" y="{y + 5.8:.2f}" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="4.5" font-weight="700" fill="#e60000">Avaliação de Viabilidade</text>',
        f'<text x="{x + w * 0.52:.2f}" y="{y + 5.8:.2f}" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="4.5" font-weight="700" fill="#e60000">* Preenchimento obrigatório com Sim, Não ou Não Avaliado</text>',
        f'<text x="{x + w - 130:.2f}" y="{y + 5.8:.2f}" font-family="Arial,Helvetica,sans-serif" font-size="4.5" font-weight="700" fill="#e60000">Viabilidade:</text>',
        f'<text x="{x + w - 16:.2f}" y="{y + 5.8:.2f}" text-anchor="end" font-family="Arial,Helvetica,sans-serif" font-size="4.5" font-weight="700" fill="#e60000">100,0%</text>',
    ]
    for idx, (question, answer) in enumerate(VIABILITY_ROWS):
        row_y = y + row_h * (idx + 1)
        if idx % 2:
            parts.append(f'<rect x="{x}" y="{row_y}" width="{w}" height="{row_h}" fill="#c9c9c9"/>')
        parts.append(
            f'<line x1="{x}" y1="{row_y}" x2="{x + w}" y2="{row_y}" stroke="#111" stroke-width="0.25"/>'
        )
        parts.append(
            f'<text x="{x + 2}" y="{row_y + 5.6:.2f}" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="4.1">{escape(question[:170])}</text>'
        )
        parts.append(
            f'<text x="{x + w - 66:.2f}" y="{row_y + 5.6:.2f}" text-anchor="middle" '
            f'font-family="Arial,Helvetica,sans-serif" font-size="4.1" font-weight="700">{escape(answer)}</text>'
        )
    parts.append(
        f'<text x="{x + 2}" y="{y + row_h * 11 + 13:.2f}" font-family="Arial,Helvetica,sans-serif" font-size="4.8">'
        "Legenda ação:    D - Desligar   L - Ligar   A - Abrir   F - Fechar   I - Incluir  E - Excluir"
        "</text>"
    )
    parts.append(
        f'<text x="{x + 2}" y="{y + row_h * 11 + 21:.2f}" font-family="Arial,Helvetica,sans-serif" font-size="4.8">'
        "Legenda Tipo Equipamento:   FC - Chave faca    FU - Chave fusível    RL - Religador    RG - Regulador    OL - Chave óleo    SC - Seccionalizadora  TR - Transformador"
        "</text>"
    )
    return "".join(parts)


def _main_equipment_label(payload: TechnicalPayload) -> str:
    return main_equipment_label_from_payload(payload)


def _main_equipment_code(payload: TechnicalPayload) -> str:
    return selected_equipment_code_from_payload(payload)
