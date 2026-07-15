from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from croqui_engine.core.models import TechnicalPayload
from croqui_engine.output.contract import (
    main_equipment_label_from_payload,
    output_header_values,
    selected_equipment_code_from_payload,
)

PAGE_SIZE = (841.68, 595.20)
VIABILITY_ROWS = [
    ("Foi realizada a avaliação do TIPO DE SOLO para permitir executar este Obra ?", "Sim"),
    (
        "Foi realizada uma AVALIAÇÃO EM CAMPO do Poste ou dos Equipamentos, se estes apresentam as "
        "condições de operação para realizar as Manobras?",
        "Sim",
    ),
    (
        "Foi realizada uma AVALIAÇÃO EM CAMPO para verificar a compatibilidade do condutor nos casos "
        "de trabalhos de equipes de Linha Viva (Solicitação /DIRA) ?",
        "Sim",
    ),
    ("Caso seja necessário uma PREPARAÇÃO para execução da Obra, ela já foi realizada?", "Sim"),
    ("Existe VEÍCULO RESERVA no dia do desligamento, caso necessite?", "Sim"),
    ("Se a execução afetar o CLIENTE, ele concorda com a intervenção?", "Sim"),
    ("O MATERIAL para esta obra está disponível?", "Sim"),
    (
        "O Tempo para execução está adequado e evita possibilidades de ATRASOS na execução ou no "
        "deslocamento para a obra?",
        "Sim",
    ),
    ("Está previsto outro DOCUMENTO RESERVA para esta obra, que será cancelado posteriormente?", "Sim"),
    ("Este documento já foi CANCELADO ou é uma Reprogramação?", "Não"),
]


def generate_final_croqui_pdf(payload: TechnicalPayload, output_path: Path) -> Path:
    try:
        from croqui_engine.rendering.svg_croqui_renderer import generate_svg_croqui_pdf

        return generate_svg_croqui_pdf(payload, output_path)
    except Exception:
        pass

    from reportlab.pdfgen import canvas

    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=PAGE_SIZE)
    _draw_page(c, payload, None)
    c.save()
    return output_path


def generate_croqui_drawing_bmp(payload: TechnicalPayload, output_path: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1300, 420), "white")
    draw = ImageDraw.Draw(img)
    try:
        small = ImageFont.truetype("Arial.ttf", 14)
    except Exception:
        small = ImageFont.load_default()

    schematic_layout = payload.meta.get("schematic_layout") or {}
    if schematic_layout.get("source") == "SchematicLayoutEngine":
        _draw_schematic_layout_pil(draw, schematic_layout, 70, 36, 1160, 340, small)
        img.save(output_path, format="BMP")
        return output_path

    layout = _project_layout(payload, 70, 36, 1160, 340)
    _draw_dynamic_network_pil(draw, payload, layout, small)
    img.save(output_path, format="BMP")
    return output_path


def _draw_page(c: Any, payload: TechnicalPayload, profile: dict[str, Any] | None) -> None:
    from reportlab.lib import colors

    width, height = PAGE_SIZE
    frame_x, frame_y = 20, 55
    frame_w, frame_h = width - 40, height - 95

    c.setFillColor(colors.white)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.rect(frame_x, frame_y, frame_w, frame_h, fill=0, stroke=1)

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(width / 2, height - 27, "Croqui")
    _draw_rge_logo(c, frame_x + 2, height - 72)
    _draw_header(c, payload, frame_x, height - 86, frame_w)
    _draw_simplified_network(c, payload)
    _draw_viability(c, profile, frame_x, frame_y, frame_w)


def _draw_header(c: Any, payload: TechnicalPayload, x: float, top_y: float, w: float) -> None:
    from reportlab.lib import colors

    h = 24
    y = top_y - h
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.4)
    c.rect(x, y, w, h, fill=0, stroke=1)
    c.line(x, y + 12, x + w, y + 12)
    for px in (x + 120, x + 270, x + 385, x + 585, x + 645):
        c.line(px, y, px, y + h)

    values = _header_values(payload)
    c.setFont("Helvetica-Bold", 4.8)
    c.drawString(x + 2, y + 14.5, "Departamento:")
    c.drawString(x + 272, y + 14.5, "Município:")
    c.drawString(x + 588, y + 14.5, "Equipamento :")
    c.drawString(x + 2, y + 3.5, "Data do Levantamento:")
    c.drawString(x + 272, y + 3.5, "Levantamento de campo realizado por:")

    c.setFont("Helvetica", 4.8)
    c.drawCentredString(x + 195, y + 14.5, values["department"])
    c.drawCentredString(x + 485, y + 14.5, values["municipality"])
    c.drawCentredString(x + 730, y + 14.5, values["equipment"])
    c.drawCentredString(x + 195, y + 3.5, values["survey_date"])
    c.drawCentredString(x + 700, y + 3.5, values["surveyor"])


def _draw_rge_logo(c: Any, x: float, y: float) -> None:
    from reportlab.lib import colors

    c.saveState()
    c.setFillColor(colors.black)
    c.setStrokeColor(colors.black)
    c.setFont("Helvetica-BoldOblique", 23)
    c.drawString(x, y, "RGE")
    c.setFont("Helvetica-Bold", 4.5)
    c.drawString(x + 43, y + 6, "Rio GrandeEnergia")
    c.setLineWidth(0.6)
    c.line(x + 86, y + 10, x + 248, y + 10)
    c.circle(x + 248, y + 10, 0.9, fill=1, stroke=1)
    c.restoreState()


def _draw_simplified_network(c: Any, payload: TechnicalPayload) -> None:
    from reportlab.lib import colors

    schematic_layout = payload.meta.get("schematic_layout") or {}
    if schematic_layout.get("source") == "SchematicLayoutEngine":
        _draw_schematic_layout_pdf(c, schematic_layout, 70, 175, 700, 285)
        return

    layout = _project_layout(payload, 70, 175, 700, 285)
    if not layout["node_positions"] and not layout["label_positions"]:
        c.setFillColor(colors.HexColor("#666666"))
        c.setFont("Helvetica", 8)
        c.drawCentredString(420, 315, "Topologia nao identificada com seguranca. Revise o payload antes da emissao.")
        return

    for start, end in _span_segments(payload, layout["node_positions"]):
        _dashed_line(c, start, end, colors.HexColor("#555555"), 0.55, 3, 2)

    if not payload.active_spans():
        ordered = sorted(layout["node_positions"].values())
        for start, end in zip(ordered, ordered[1:], strict=False):
            _dashed_line(c, start, end, colors.HexColor("#999999"), 0.45, 2, 3)

    for node in payload.active_nodes():
        point = layout["node_positions"].get(node.id)
        if not point:
            continue
        _draw_pole(c, *point)
        _draw_label(c, node.id, point[0] - 5, point[1] - 13)

    for item in layout["label_positions"][:24]:
        _draw_label(c, item["text"], item["point"][0] + 4, item["point"][1] - 10)

    equipment_points = _equipment_points(payload, layout)
    for equipment, point in equipment_points:
        _draw_switch(c, point[0], point[1] + 9, angle=_equipment_angle(payload, equipment, layout))
        _draw_label(c, equipment.code, point[0] + 5, point[1] + 19)

    if equipment_points:
        _draw_dynamic_work_area(c, _primary_equipment_points(payload, equipment_points), layout)


def _draw_schematic_layout_pdf(
    c: Any,
    layout: dict[str, Any],
    x: float,
    y: float,
    w: float,
    h: float,
) -> None:
    from reportlab.lib import colors

    nodes = layout.get("nodes") or []
    edges = layout.get("edges") or []
    labels = layout.get("labels") or []
    work_zones = layout.get("work_zones") or []
    if not nodes:
        c.setFillColor(colors.HexColor("#666666"))
        c.setFont("Helvetica", 8)
        c.drawCentredString(x + w / 2, y + h / 2, "Topologia esquematica nao identificada com seguranca.")
        return

    project, size_project = _schematic_projectors(layout, x, y, w, h, invert_y=True)
    node_by_id = {str(node.get("id") or ""): node for node in nodes}
    for edge in edges:
        points = edge.get("points") or []
        if len(points) < 2:
            start = node_by_id.get(str(edge.get("from_node") or ""))
            end = node_by_id.get(str(edge.get("to_node") or ""))
            if not start or not end:
                continue
            points = [(start.get("x"), start.get("y")), (end.get("x"), end.get("y"))]
        mapped = [project(float(px), float(py)) for px, py in points]
        c.setStrokeColor(colors.HexColor("#303438"))
        c.setLineWidth(0.7 if edge.get("type") != "EQUIPAMENTO" else 0.55)
        if str(edge.get("type") or "").endswith("INFERIDA"):
            c.setDash(3, 2)
        else:
            c.setDash()
        path = c.beginPath()
        path.moveTo(*mapped[0])
        for point in mapped[1:]:
            path.lineTo(*point)
        c.drawPath(path, stroke=1, fill=0)
        c.setDash()

    for node in nodes:
        nx, ny = project(float(node.get("x") or 0), float(node.get("y") or 0))
        _draw_schematic_node_pdf(c, node, nx, ny)

    for label in labels:
        lx, ly = project(float(label.get("x") or 0), float(label.get("y") or 0))
        _draw_label(c, str(label.get("text") or ""), lx, ly, bold=label.get("role") == "focus_label")

    for zone in work_zones:
        zx, zy = project(float(zone.get("x") or 0), float(zone.get("y") or 0))
        zw, zh = size_project(float(zone.get("width") or 0), float(zone.get("height") or 0))
        _draw_work_area(c, (zx, zy), zw, zh, -float(zone.get("angle") or -12))
        _draw_red_intervention_marks_at(c, (zx, zy))


def _draw_schematic_layout_pil(
    draw: Any,
    layout: dict[str, Any],
    x: float,
    y: float,
    w: float,
    h: float,
    font: Any,
) -> None:
    nodes = layout.get("nodes") or []
    edges = layout.get("edges") or []
    labels = layout.get("labels") or []
    work_zones = layout.get("work_zones") or []
    project, size_project = _schematic_projectors(layout, x, y, w, h, invert_y=False)
    node_by_id = {str(node.get("id") or ""): node for node in nodes}

    for edge in edges:
        points = edge.get("points") or []
        if len(points) < 2:
            start = node_by_id.get(str(edge.get("from_node") or ""))
            end = node_by_id.get(str(edge.get("to_node") or ""))
            if not start or not end:
                continue
            points = [(start.get("x"), start.get("y")), (end.get("x"), end.get("y"))]
        mapped = [_to_int_point(project(float(px), float(py))) for px, py in points]
        if str(edge.get("type") or "").endswith("INFERIDA"):
            for start, end in zip(mapped, mapped[1:], strict=False):
                _pil_dashed_line(draw, start, end, fill=(80, 80, 80), width=2, dash=8)
        else:
            draw.line(mapped, fill=(40, 44, 48), width=2)

    for node in nodes:
        nx, ny = _to_int_point(project(float(node.get("x") or 0), float(node.get("y") or 0)))
        _draw_schematic_node_pil(draw, node, (nx, ny), font)

    for label in labels:
        lx, ly = _to_int_point(project(float(label.get("x") or 0), float(label.get("y") or 0)))
        draw.text((lx, ly), str(label.get("text") or ""), fill=(0, 0, 0), font=font)

    for zone in work_zones:
        zx, zy = _to_int_point(project(float(zone.get("x") or 0), float(zone.get("y") or 0)))
        zw, zh = size_project(float(zone.get("width") or 0), float(zone.get("height") or 0))
        _pil_rotated_rect(
            draw,
            (zx, zy),
            int(round(zw)),
            int(round(zh)),
            float(zone.get("angle") or -12),
            outline=(255, 0, 0),
            dash=8,
        )
        _pil_red_intervention_marks_at(draw, (zx, zy))


def _schematic_projectors(
    layout: dict[str, Any],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    invert_y: bool,
) -> tuple[Any, Any]:
    canvas = layout.get("canvas") or {}
    canvas_w = float(canvas.get("width") or 1000.0)
    canvas_h = float(canvas.get("height") or 420.0)

    def project(px: float, py: float) -> tuple[float, float]:
        mapped_y = canvas_h - py if invert_y else py
        return x + (px / canvas_w) * w, y + (mapped_y / canvas_h) * h

    def size_project(width: float, height: float) -> tuple[float, float]:
        return (width / canvas_w) * w, (height / canvas_h) * h

    return project, size_project


def _draw_schematic_node_pdf(c: Any, node: dict[str, Any], x: float, y: float) -> None:
    from reportlab.lib import colors

    node_type = str(node.get("type") or "").upper()
    if node.get("is_focus"):
        c.setStrokeColor(colors.red)
        c.setLineWidth(0.7)
        c.setDash(2, 2)
        c.circle(x, y, 12, fill=0, stroke=1)
        c.setDash()
    if node_type in {"POSTE", "EQUIPAMENTO_REFERENCIA"}:
        _draw_pole(c, x, y)
    elif node_type in {"TR", "TRANSFORMADOR"}:
        c.setStrokeColor(colors.black)
        c.setFillColor(colors.white)
        c.setLineWidth(0.65)
        c.rect(x - 7, y - 6, 14, 12, fill=1, stroke=1)
        c.circle(x - 3, y, 2.8, fill=0, stroke=1)
        c.circle(x + 3, y, 2.8, fill=0, stroke=1)
    elif node_type in {"FU", "FC", "CF", "RL", "SC"}:
        _draw_switch(c, x, y, 0)
        c.setFont("Helvetica", 4.2)
        c.drawCentredString(x, y - 11, "FC" if node_type == "CF" else node_type[:2])
    else:
        c.setStrokeColor(colors.black)
        c.setFillColor(colors.white)
        c.rect(x - 4, y - 4, 8, 8, fill=1, stroke=1)


def _draw_schematic_node_pil(
    draw: Any,
    node: dict[str, Any],
    point: tuple[int, int],
    font: Any,
) -> None:
    x, y = point
    node_type = str(node.get("type") or "").upper()
    if node.get("is_focus"):
        draw.ellipse((x - 21, y - 21, x + 21, y + 21), outline=(255, 0, 0), width=2)
    if node_type in {"POSTE", "EQUIPAMENTO_REFERENCIA"}:
        _pil_pole(draw, point)
    elif node_type in {"TR", "TRANSFORMADOR"}:
        draw.rectangle((x - 14, y - 12, x + 14, y + 12), fill=(255, 255, 255), outline=(0, 0, 0), width=2)
        draw.ellipse((x - 10, y - 6, x - 1, y + 6), outline=(0, 0, 0), width=1)
        draw.ellipse((x + 1, y - 6, x + 10, y + 6), outline=(0, 0, 0), width=1)
    elif node_type in {"FU", "FC", "CF", "RL", "SC"}:
        _pil_switch(draw, point, 0)
        draw.text((x - 10, y + 12), "FC" if node_type == "CF" else node_type[:2], fill=(0, 0, 0), font=font)
    else:
        draw.rectangle((x - 8, y - 8, x + 8, y + 8), fill=(255, 255, 255), outline=(0, 0, 0), width=2)


def _project_layout(payload: TechnicalPayload, x: float, y: float, w: float, h: float) -> dict[str, Any]:
    node_sources = {
        node.id: (float(node.x), float(node.y))
        for node in payload.active_nodes()
        if node.x is not None and node.y is not None
    }
    label_sources = _label_sources(payload, node_sources)
    equipment_sources = [
        (float(eq.bbox.center[0]), float(eq.bbox.center[1]))
        for eq in payload.active_equipment()
        if eq.bbox is not None
    ]
    source_points = [*node_sources.values(), *equipment_sources]
    source_points.extend((item["x"], item["y"]) for item in label_sources)
    if not source_points:
        return {
            "node_positions": {},
            "label_positions": [],
            "scale": lambda pt: pt,
            "bounds": None,
            "frame": (x, y, w, h),
        }

    min_x = min(point[0] for point in source_points)
    max_x = max(point[0] for point in source_points)
    min_y = min(point[1] for point in source_points)
    max_y = max(point[1] for point in source_points)
    if max_x - min_x < 1:
        max_x += 1
    if max_y - min_y < 1:
        max_y += 1
    pad_x = (max_x - min_x) * 0.12
    pad_y = (max_y - min_y) * 0.18
    min_x -= pad_x
    max_x += pad_x
    min_y -= pad_y
    max_y += pad_y
    raw_w = max(max_x - min_x, 1)
    raw_h = max(max_y - min_y, 1)
    scale = min(w / raw_w, h / raw_h)
    used_w = raw_w * scale
    used_h = raw_h * scale
    x0 = x + (w - used_w) / 2
    y0 = y + (h - used_h) / 2

    def project(point: tuple[float, float]) -> tuple[float, float]:
        sx, sy = point
        return (
            x0 + (sx - min_x) * scale,
            y0 + (max_y - sy) * scale,
        )

    return {
        "node_positions": {node_id: project(point) for node_id, point in node_sources.items()},
        "label_positions": [
            {"text": item["text"], "point": project((item["x"], item["y"]))}
            for item in label_sources
        ],
        "scale": project,
        "bounds": (min_x, min_y, max_x, max_y),
        "frame": (x, y, w, h),
    }


def _label_sources(payload: TechnicalPayload, node_sources: dict[str, tuple[float, float]]) -> list[dict[str, Any]]:
    raw_items = payload.meta.get("project_numeric_label_positions") or []
    if not raw_items:
        return []
    equipment_codes = {equipment.code for equipment in payload.active_equipment()}
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_items:
        text = str(item.get("text") or "")
        if not text or text in seen:
            continue
        x = float(item.get("x") or 0)
        y = float(item.get("y") or 0)
        if text in equipment_codes or _near_any_node((x, y), node_sources):
            selected.append({"text": text, "x": x, "y": y})
            seen.add(text)
    if selected:
        return selected[:24]
    for item in raw_items[:16]:
        text = str(item.get("text") or "")
        if not text or text in seen:
            continue
        selected.append({"text": text, "x": float(item.get("x") or 0), "y": float(item.get("y") or 0)})
        seen.add(text)
    return selected


def _near_any_node(point: tuple[float, float], node_sources: dict[str, tuple[float, float]]) -> bool:
    if not node_sources:
        return True
    px, py = point
    return any(math.hypot(px - nx, py - ny) <= 260 for nx, ny in node_sources.values())


def _span_segments(
    payload: TechnicalPayload,
    node_positions: dict[str, tuple[float, float]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    segments = []
    for span in payload.active_spans():
        start = node_positions.get(span.from_node)
        end = node_positions.get(span.to_node)
        if start and end:
            segments.append((start, end))
    return segments


def _equipment_points(
    payload: TechnicalPayload,
    layout: dict[str, Any],
) -> list[tuple[Any, tuple[float, float]]]:
    points = []
    node_positions = layout["node_positions"]
    label_positions = {item["text"]: item["point"] for item in layout["label_positions"]}
    project = layout["scale"]
    fallback_nodes = list(node_positions.values())
    for idx, equipment in enumerate(payload.active_equipment()):
        point = None
        if equipment.node_id:
            point = node_positions.get(equipment.node_id)
        if point is None and equipment.bbox is not None:
            point = project((float(equipment.bbox.center[0]), float(equipment.bbox.center[1])))
        if point is None:
            point = label_positions.get(equipment.code)
        if point is None and fallback_nodes:
            point = fallback_nodes[min(idx, len(fallback_nodes) - 1)]
        if point is not None:
            points.append((equipment, point))
    return points


def _equipment_angle(payload: TechnicalPayload, equipment: Any, layout: dict[str, Any]) -> float:
    if not equipment.node_id:
        return 25
    node_positions = layout["node_positions"]
    origin = node_positions.get(equipment.node_id)
    if not origin:
        return 25
    for span in payload.active_spans():
        other_id = None
        if span.from_node == equipment.node_id:
            other_id = span.to_node
        elif span.to_node == equipment.node_id:
            other_id = span.from_node
        if other_id and other_id in node_positions:
            other = node_positions[other_id]
            return math.degrees(math.atan2(other[1] - origin[1], other[0] - origin[0]))
    return 25


def _primary_equipment_points(
    payload: TechnicalPayload,
    equipment_points: list[tuple[Any, tuple[float, float]]],
) -> list[tuple[float, float]]:
    selected_code = selected_equipment_code_from_payload(payload)
    for equipment, point in equipment_points:
        if selected_code and equipment.code == selected_code:
            return [point]
    for equipment, point in equipment_points:
        if equipment.type != "TRANSFORMADOR":
            return [point]
    return [equipment_points[0][1]]


def _draw_dynamic_work_area(c: Any, points: list[tuple[float, float]], layout: dict[str, Any]) -> None:
    if not points:
        return
    cx = sum(point[0] for point in points) / len(points)
    cy = sum(point[1] for point in points) / len(points)
    nearby = _nearby_label_points((cx, cy), layout, radius=70, limit=2)
    all_points = [*points, *nearby]
    min_x = min(point[0] for point in all_points) - 30
    max_x = max(point[0] for point in all_points) + 30
    min_y = min(point[1] for point in all_points) - 25
    max_y = max(point[1] for point in all_points) + 25
    _draw_work_area(
        c,
        center=((min_x + max_x) / 2, (min_y + max_y) / 2),
        width=max(max_x - min_x, 70),
        height=max(max_y - min_y, 48),
        angle=-18,
    )
    _draw_red_intervention_marks_at(c, (cx, cy))


def _draw_red_intervention_marks_at(c: Any, center: tuple[float, float]) -> None:
    from reportlab.lib import colors

    cx, cy = center
    c.setStrokeColor(colors.red)
    c.setLineWidth(0.6)
    for dx, dy, angle in [(-18, 10, -25), (10, -2, -25), (28, 16, -25)]:
        c.saveState()
        c.translate(cx + dx, cy + dy)
        c.rotate(angle)
        c.line(-12, 0, 12, 0)
        c.line(4, -4, 12, 0)
        c.line(4, 4, 12, 0)
        c.restoreState()


def _draw_dynamic_network_pil(draw: Any, payload: TechnicalPayload, layout: dict[str, Any], font: Any) -> None:
    for start, end in _span_segments(payload, layout["node_positions"]):
        _pil_dashed_line(draw, _to_int_point(start), _to_int_point(end), fill=(90, 90, 90), width=2, dash=8)
    if not payload.active_spans():
        ordered = sorted(layout["node_positions"].values())
        for start, end in zip(ordered, ordered[1:], strict=False):
            _pil_dashed_line(draw, _to_int_point(start), _to_int_point(end), fill=(150, 150, 150), width=2, dash=8)
    for node in payload.active_nodes():
        point = layout["node_positions"].get(node.id)
        if not point:
            continue
        int_point = _to_int_point(point)
        _pil_pole(draw, int_point)
        draw.text((int_point[0] - 8, int_point[1] + 10), node.id, fill=(0, 0, 0), font=font)
    for item in layout["label_positions"][:24]:
        point = _to_int_point(item["point"])
        draw.text((point[0] + 6, point[1] - 12), item["text"], fill=(0, 0, 0), font=font)
    equipment_points = _equipment_points(payload, layout)
    for equipment, point in equipment_points:
        int_point = _to_int_point(point)
        _pil_switch(draw, (int_point[0], int_point[1] - 12), angle=int(_equipment_angle(payload, equipment, layout)))
        draw.text((int_point[0] + 8, int_point[1] - 26), equipment.code, fill=(0, 0, 0), font=font)
    if equipment_points:
        _pil_dynamic_work_area(draw, _primary_equipment_points(payload, equipment_points), layout)


def _pil_dynamic_work_area(draw: Any, points: list[tuple[float, float]], layout: dict[str, Any]) -> None:
    if not points:
        return
    cx = sum(point[0] for point in points) / len(points)
    cy = sum(point[1] for point in points) / len(points)
    nearby = _nearby_label_points((cx, cy), layout, radius=110, limit=2)
    all_points = [*points, *nearby]
    min_x = min(point[0] for point in all_points) - 42
    max_x = max(point[0] for point in all_points) + 42
    min_y = min(point[1] for point in all_points) - 36
    max_y = max(point[1] for point in all_points) + 36
    center = (int((min_x + max_x) / 2), int((min_y + max_y) / 2))
    _pil_rotated_rect(
        draw,
        center,
        int(max(max_x - min_x, 110)),
        int(max(max_y - min_y, 80)),
        -18,
        outline=(255, 0, 0),
        dash=8,
    )
    _pil_red_intervention_marks_at(draw, center)


def _nearby_label_points(
    center: tuple[float, float],
    layout: dict[str, Any],
    radius: float,
    limit: int,
) -> list[tuple[float, float]]:
    cx, cy = center
    label_points = [item["point"] for item in layout["label_positions"]]
    nearby = [
        point
        for point in sorted(label_points, key=lambda item: math.hypot(item[0] - cx, item[1] - cy))
        if math.hypot(point[0] - cx, point[1] - cy) <= radius
    ]
    return nearby[:limit]


def _to_int_point(point: tuple[float, float]) -> tuple[int, int]:
    return (int(round(point[0])), int(round(point[1])))


def _pil_red_intervention_marks_at(draw: Any, center: tuple[int, int]) -> None:
    cx, cy = center
    for dx, dy in [(-28, 12), (8, -10), (34, 18)]:
        start = (cx + dx - 20, cy + dy - 6)
        end = (cx + dx + 20, cy + dy + 6)
        draw.line([start, end], fill=(255, 0, 0), width=2)
        draw.line([(end[0] - 10, end[1] - 8), end], fill=(255, 0, 0), width=2)
        draw.line([(end[0] - 12, end[1] + 5), end], fill=(255, 0, 0), width=2)


def _draw_viability(c: Any, profile: dict[str, Any] | None, x: float, y: float, w: float) -> None:
    from reportlab.lib import colors

    rows = _viability_rows(profile)
    row_h = 8.1
    table_h = row_h * (len(rows) + 1)
    table_y = y
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.35)
    c.rect(x, table_y, w, table_h, fill=0, stroke=1)
    header_y = table_y + table_h - row_h
    c.setFillColor(colors.HexColor("#FFF36D"))
    c.rect(x, header_y, w, row_h, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 4.5)
    c.setFillColor(colors.red)
    c.drawCentredString(x + w * 0.36, header_y + 2.3, "Avaliação de Viabilidade")
    c.drawCentredString(x + w * 0.52, header_y + 2.3, "* Preenchimento obrigatório com Sim, Não ou Não Avaliado")
    c.drawString(x + w - 130, header_y + 2.3, "Viabilidade:")
    c.drawRightString(x + w - 16, header_y + 2.3, "100,0%")

    answer_x = x + w - 112
    c.setFillColor(colors.black)
    for idx, (question, answer) in enumerate(rows):
        row_y = header_y - (idx + 1) * row_h
        if idx % 2:
            c.setFillColor(colors.HexColor("#C9C9C9"))
            c.rect(x, row_y, w, row_h, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 4.1)
        c.drawString(x + 2, row_y + 2.1, question[:170])
        c.setFont("Helvetica-Bold", 4.2)
        c.drawCentredString(answer_x + 46, row_y + 2.1, answer)
        c.line(x, row_y, x + w, row_y)

    legend_y = table_y - 11
    c.setFont("Helvetica", 4.5)
    c.drawString(
        x + 2,
        legend_y,
        "Legenda ação:    D - Desligar   L - Ligar   A - Abrir   F - Fechar   I - Incluir  E - Excluir",
    )
    c.drawString(
        x + 2,
        legend_y - 8,
        "Legenda Tipo Equipamento:   FC - Chave faca    FU - Chave fusível    RL - Religador    "
        "RG - Regulador    OL - Chave óleo    SC - Seccionalizadora  TR - Transformador",
    )


def _header_values(payload: TechnicalPayload) -> dict[str, str]:
    return output_header_values(payload)


def _main_equipment_label(payload: TechnicalPayload) -> str:
    return main_equipment_label_from_payload(payload)


def _label_set(payload: TechnicalPayload) -> set[str]:
    labels: set[str] = set()
    for raw in payload.meta.get("project_numeric_labels") or []:
        labels.add(str(raw).upper())
    for eq in payload.active_equipment():
        if eq.code:
            labels.add(eq.code)
    return labels


def _graph_labels(payload: TechnicalPayload, labels: set[str]) -> dict[str, str]:
    main_code = selected_equipment_code_from_payload(payload)
    if not main_code:
        main_code = str(payload.meta.get("main_switching_equipment") or "").split()[-1]
    numeric = [label for label in sorted(labels) if label.isdigit() and label != main_code]
    preferred = {
        "baseline": _pick(numeric, set(), 0),
        "area_equipment": _pick(numeric, set(), 1),
        "center_branch": _pick(numeric, set(), 2),
        "left_branch": _pick(numeric, set(), 3),
    }
    return {
        "main": main_code,
        "baseline": preferred["baseline"],
        "area_equipment": preferred["area_equipment"],
        "center_branch": preferred["center_branch"],
        "left_branch": preferred["left_branch"],
    }


def _pick(values: list[str], preferred: set[str], fallback_index: int) -> str:
    for value in values:
        if value in preferred:
            return value
    return values[fallback_index] if fallback_index < len(values) else ""


def _viability_rows(profile: dict[str, Any] | None) -> list[tuple[str, str]]:
    rows = []
    for row in (profile or {}).get("viability", {}).get("rows", []):
        question = str(row.get("question") or "").strip()
        answer = str(row.get("answer") or "").strip()
        if question:
            rows.append((question, answer or "Sim"))
    return rows or VIABILITY_ROWS


def _draw_pole(c: Any, x: float, y: float) -> None:
    from reportlab.lib import colors

    c.setStrokeColor(colors.black)
    c.setFillColor(colors.white)
    c.setLineWidth(0.5)
    c.circle(x, y, 3.0, fill=1, stroke=1)
    c.circle(x, y, 1.0, fill=0, stroke=1)


def _draw_switch(c: Any, x: float, y: float, angle: float) -> None:
    from reportlab.lib import colors

    c.saveState()
    c.translate(x, y)
    c.rotate(angle)
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.7)
    c.line(-8, 0, 8, 0)
    c.line(-2, 0, 4, 5)
    c.circle(-8, 0, 1.4, fill=1, stroke=1)
    c.circle(8, 0, 1.4, fill=1, stroke=1)
    c.restoreState()


def _draw_label(c: Any, text: str, x: float, y: float, fill: Any | None = None, bold: bool = False) -> None:
    from reportlab.lib import colors

    c.setFillColor(fill or colors.black)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", 4.8)
    c.drawString(x, y, text)


def _draw_work_area(c: Any, center: tuple[float, float], width: float, height: float, angle: float) -> None:
    from reportlab.lib import colors

    points = _rotated_rect_points(center, width, height, angle)
    c.setStrokeColor(colors.red)
    c.setLineWidth(1.0)
    c.setDash(2, 3)
    path = c.beginPath()
    path.moveTo(*points[0])
    for point in points[1:]:
        path.lineTo(*point)
    path.close()
    c.drawPath(path, fill=0, stroke=1)
    c.setDash()


def _draw_red_intervention_marks(c: Any) -> None:
    from reportlab.lib import colors

    c.setStrokeColor(colors.red)
    c.setLineWidth(0.6)
    for x, y, angle in [(455, 424, -35), (480, 411, -35), (497, 435, -35)]:
        c.saveState()
        c.translate(x, y)
        c.rotate(angle)
        c.line(-12, 0, 12, 0)
        c.line(4, -4, 12, 0)
        c.line(4, 4, 12, 0)
        c.restoreState()


def _dashed_line(c: Any, a: tuple[float, float], b: tuple[float, float], color: Any, width: float, dash: float, gap: float) -> None:
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.setDash(dash, gap)
    c.line(a[0], a[1], b[0], b[1])
    c.setDash()


def _rotated_rect_points(
    center: tuple[float, float], width: float, height: float, angle: float
) -> list[tuple[float, float]]:
    cx, cy = center
    theta = math.radians(angle)
    ct, st = math.cos(theta), math.sin(theta)
    raw = [(-width / 2, -height / 2), (width / 2, -height / 2), (width / 2, height / 2), (-width / 2, height / 2)]
    return [(cx + px * ct - py * st, cy + px * st + py * ct) for px, py in raw]


def _pil_pole(draw: Any, point: tuple[int, int]) -> None:
    x, y = point
    draw.ellipse((x - 7, y - 7, x + 7, y + 7), outline=(0, 0, 0), width=2)
    draw.ellipse((x - 2, y - 2, x + 2, y + 2), outline=(0, 0, 0), width=1)


def _pil_switch(draw: Any, point: tuple[int, int], angle: float) -> None:
    x, y = point
    theta = math.radians(angle)
    ct, st = math.cos(theta), math.sin(theta)

    def rot(px: float, py: float) -> tuple[float, float]:
        return x + px * ct - py * st, y + px * st + py * ct

    draw.line([rot(-14, 0), rot(14, 0)], fill=(0, 0, 0), width=2)
    draw.line([rot(-2, 0), rot(8, 8)], fill=(0, 0, 0), width=2)


def _pil_dashed_line(
    draw: Any, start: tuple[int, int], end: tuple[int, int], fill: tuple[int, int, int], width: int, dash: int
) -> None:
    x1, y1 = start
    x2, y2 = end
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return
    vx, vy = (x2 - x1) / length, (y2 - y1) / length
    dist = 0
    while dist < length:
        a = dist
        b = min(dist + dash, length)
        draw.line([(x1 + vx * a, y1 + vy * a), (x1 + vx * b, y1 + vy * b)], fill=fill, width=width)
        dist += dash * 1.8


def _pil_rotated_rect(
    draw: Any,
    center: tuple[int, int],
    width: int,
    height: int,
    angle: float,
    outline: tuple[int, int, int],
    dash: int,
) -> None:
    pts = _rotated_rect_points(center, width, height, angle)
    for a, b in zip(pts, [*pts[1:], pts[0]], strict=False):
        _pil_dashed_line(draw, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), outline, 2, dash)


def _pil_red_marks(draw: Any) -> None:
    for start, end in [((625, 325), (675, 350)), ((665, 305), (715, 270)), ((705, 330), (755, 345))]:
        draw.line([start, end], fill=(255, 0, 0), width=2)
