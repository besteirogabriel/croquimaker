from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.colors import black, blue, red, white, Color, HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from sistema.parsing.entities import ExistingEquipment, Position, ProjectExtraction, Transformer


PAGE_W, PAGE_H = landscape(A4)
GREEN = HexColor("#165d2c")
LIGHT_GREEN = HexColor("#e7f2e9")
LIGHT_GRAY = HexColor("#d7d7d7")
ORANGE = HexColor("#f07d19")


@dataclass(frozen=True)
class SourceRect:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True)
class WorkArea:
    index: int
    kind: str
    label: str
    observation: str
    positions: tuple[Position, ...]


@dataclass(frozen=True)
class WorkAreaStyle:
    color: Color
    shape: str


def _numeric_code(value: str) -> str:
    match = re.search(r"\b(\d{6,7})\b", str(value))
    return match.group(1) if match else ""


def _page_y(position: Position, extraction: ProjectExtraction) -> float:
    return position.y_pdf(extraction.page_sizes[position.page][1])


def _all_equipment(extraction: ProjectExtraction) -> list[Transformer | ExistingEquipment]:
    by_code: dict[str, Transformer | ExistingEquipment] = {}
    for equipment in [*extraction.transformers, *extraction.existing_equipment]:
        if equipment.numero and equipment.numero not in by_code:
            by_code[equipment.numero] = equipment
    return list(by_code.values())


def _semantic_codes(projeto: dict) -> list[str]:
    codes: list[str] = []
    meta = projeto.get("meta", {}) if isinstance(projeto, dict) else {}
    for raw in [meta.get("equipamento", ""), *[e.get("codigo", "") for e in projeto.get("equipamentos", []) if isinstance(e, dict)]]:
        code = _numeric_code(raw)
        if code and code not in codes:
            codes.append(code)
    return codes


def _equipment_by_code(
    extraction: ProjectExtraction,
) -> dict[str, Transformer | ExistingEquipment]:
    return {item.numero: item for item in _all_equipment(extraction) if item.numero}


def _fold_ascii(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", str(value))
        if not unicodedata.combining(character)
    )


def _area_kind(area: dict) -> str:
    text = _fold_ascii(" ".join(
        str(area.get(key, "")) for key in ("tipo", "nome", "observacao")
    )).upper()
    if re.search(r"\bLV\b|LINHA\s+VIVA", text):
        return "LV"
    if re.search(r"\bLM\b|LINHA\s+MORTA", text):
        return "LM"
    raw_type = re.sub(
        r"[^A-Z0-9_-]", "", _fold_ascii(area.get("tipo", "")).upper()
    )
    return raw_type or "TRABALHO"


def _area_style(kind: str) -> WorkAreaStyle:
    if kind == "LV":
        return WorkAreaStyle(color=blue, shape="ellipse")
    if kind == "LM":
        return WorkAreaStyle(color=red, shape="rect")
    return WorkAreaStyle(color=GREEN, shape="rect")


def _area_label(area: dict, index: int, kind: str) -> str:
    raw = re.sub(r"\s+", " ", str(area.get("nome", "")).strip()).upper()
    normalized = re.sub(r"[^A-Z0-9 ]", "", _fold_ascii(raw))
    generic = not raw or normalized in {
        "AREA",
        "AREA DE TRABALHO",
        "AREA DE INTERVENCAO",
        "TRABALHO",
        "LM",
        "LV",
    }
    if generic or normalized.startswith("AREA DE TRABALHO"):
        label = f"AREA DE TRABALHO {index}"
    else:
        label = raw
    if kind != "TRABALHO" and not re.search(rf"\b{re.escape(kind)}\b", label):
        label = f"{label} {kind}"
    return label[:80]


def _area_node_ids(area: dict) -> list[str]:
    return list(
        dict.fromkeys(
            f"P{int(number)}"
            for number in re.findall(r"\bP\s*0*(\d+)\b", str(area.get("nos", "")), re.I)
        )
    )


def _dedupe_positions(positions: list[Position]) -> tuple[Position, ...]:
    seen: set[tuple[int, int, int]] = set()
    result: list[Position] = []
    for position in positions:
        key = (position.page, round(position.x * 10), round(position.y * 10))
        if key in seen:
            continue
        seen.add(key)
        result.append(position)
    return tuple(result)


def _resolve_work_areas(
    extraction: ProjectExtraction, projeto: dict, page_no: int
) -> list[WorkArea]:
    raw_areas = projeto.get("areas", []) if isinstance(projeto, dict) else []
    areas = [area for area in raw_areas if isinstance(area, dict)]
    if not areas:
        return []

    poles_by_code = {
        pole.codigo: pole.position
        for pole in extraction.poles
        if pole.position.page == page_no and pole.codigo.startswith("P")
    }
    equipment_by_code = _equipment_by_code(extraction)
    semantic_equipment = [
        row
        for row in projeto.get("equipamentos", [])
        if isinstance(row, dict)
    ]

    resolved: list[WorkArea] = []
    for index, area in enumerate(areas, start=1):
        kind = _area_kind(area)
        node_ids = _area_node_ids(area)
        positions = [poles_by_code[node_id] for node_id in node_ids if node_id in poles_by_code]

        # Equipment-to-node relationships from the semantic result are more
        # precise than a generic proximity fallback.
        if node_ids:
            for row in semantic_equipment:
                if str(row.get("no_id", "")) not in node_ids:
                    continue
                code = _numeric_code(row.get("codigo", ""))
                equipment = equipment_by_code.get(code)
                if equipment and equipment.position.page == page_no:
                    positions.append(equipment.position)

        # An area observation may identify an operative number directly.
        area_text = " ".join(str(value) for value in area.values())
        for code in re.findall(r"\b\d{6,7}\b", area_text):
            equipment = equipment_by_code.get(code)
            if equipment and equipment.position.page == page_no:
                positions.append(equipment.position)

        # For a single declared area, the primary work equipment is a safe
        # fallback. With multiple unresolved areas we omit the overlay instead
        # of inventing different positions; their data-driven legend remains.
        if not positions and len(areas) == 1:
            primary_codes = [
                *_semantic_codes(projeto),
                _numeric_code(extraction.metadata.get("equipamento", "")),
            ]
            for code in primary_codes:
                equipment = equipment_by_code.get(code)
                if equipment and equipment.position.page == page_no:
                    positions.append(equipment.position)
                    break

        resolved.append(
            WorkArea(
                index=index,
                kind=kind,
                label=_area_label(area, index, kind),
                observation=re.sub(
                    r"\s+", " ", str(area.get("observacao", "")).strip()
                )[:180],
                positions=_dedupe_positions(positions),
            )
        )
    return resolved


def _choose_page(extraction: ProjectExtraction, projeto: dict) -> int:
    equipment_by_code = _equipment_by_code(extraction)
    for code in [
        *_semantic_codes(projeto),
        _numeric_code(extraction.metadata.get("equipamento", "")),
    ]:
        equipment = equipment_by_code.get(code)
        if equipment:
            return equipment.position.page
    return max(
        extraction.page_sizes,
        key=lambda page: sum(
            segment.length for segment in extraction.conductors if segment.page == page
        ),
    )


def _choose_anchors(
    extraction: ProjectExtraction,
    projeto: dict,
    page_no: int,
    extra_positions: tuple[Position, ...] = (),
) -> list[Position]:
    equipment = [e for e in _all_equipment(extraction) if e.position.page == page_no]
    by_code = {e.numero: e.position for e in equipment}
    semantic_codes = _semantic_codes(projeto)
    metadata_code = _numeric_code(extraction.metadata.get("equipamento", ""))

    primary = next((by_code[c] for c in [*semantic_codes, metadata_code] if c in by_code), None)
    if primary is None and extraction.transformers:
        primary = next((t.position for t in extraction.transformers if t.position.page == page_no), None)
    if primary is None and extraction.poles:
        primary = next((p.position for p in extraction.poles if p.position.page == page_no), None)
    if primary is None:
        width, height = extraction.page_sizes[page_no]
        return [Position.from_pdf(page_no, width / 2, height / 2, height)]

    anchors = [primary]
    page_height = extraction.page_sizes[page_no][1]
    page_width = extraction.page_sizes[page_no][0]
    px, py = primary.x, primary.y_pdf(page_height)
    context_radius = min(page_width, page_height) * 0.39
    ordinary_radius = min(page_width, page_height) * 0.30
    # Inclui os demais equipamentos do mesmo conjunto de trabalho sem permitir
    # que um codigo remoto expanda o croqui para a folha inteira.
    for equipment_item in equipment:
        pos = equipment_item.position
        distance = math.hypot(pos.x - px, pos.y_pdf(page_height) - py)
        context = getattr(equipment_item, "contexto", "").upper()
        is_work_item = (
            equipment_item.numero in semantic_codes
            or getattr(equipment_item, "novo", False)
            or "INSTALAR" in context
            or "NOVO" in context
        )
        if distance <= context_radius and (distance <= ordinary_radius or is_work_item):
            if pos not in anchors:
                anchors.append(pos)
    for position in extra_positions:
        if position.page == page_no and position not in anchors:
            anchors.append(position)
    return anchors


def _source_region(extraction: ProjectExtraction, page_no: int, anchors: list[Position]) -> SourceRect:
    width, height = extraction.page_sizes[page_no]
    anchor_points = [(p.x, p.y_pdf(height)) for p in anchors]
    radius = min(width, height) * 0.46
    selected = []
    for pole in extraction.poles:
        if pole.position.page != page_no:
            continue
        x = pole.position.x
        y = pole.position.y_pdf(height)
        if min(math.hypot(x - ax, y - ay) for ax, ay in anchor_points) <= radius:
            selected.append((x, y))
    points = [*anchor_points, *selected]
    min_x = min(p[0] for p in points)
    max_x = max(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_y = max(p[1] for p in points)

    min_width = width * 0.64
    min_height = height * 0.77
    margin = min(width, height) * 0.033
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    half_w = max((max_x - min_x) / 2 + margin, min_width / 2)
    half_h = max((max_y - min_y) / 2 + margin, min_height / 2)
    x0, x1 = cx - half_w, cx + half_w
    y0, y1 = cy - half_h, cy + half_h
    if x0 < 0:
        x1 -= x0
        x0 = 0
    if x1 > width:
        x0 -= x1 - width
        x1 = width
    if y0 < 0:
        y1 -= y0
        y0 = 0
    if y1 > height:
        y0 -= y1 - height
        y1 = height
    return SourceRect(max(0, x0), max(0, y0), min(width, x1), min(height, y1))


def _clip_line(rect: SourceRect, x1: float, y1: float, x2: float, y2: float):
    dx, dy = x2 - x1, y2 - y1
    p = (-dx, dx, -dy, dy)
    q = (x1 - rect.x0, rect.x1 - x1, y1 - rect.y0, rect.y1 - y1)
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if abs(pi) < 1e-12:
            if qi < 0:
                return None
            continue
        t = qi / pi
        if pi < 0:
            u1 = max(u1, t)
        else:
            u2 = min(u2, t)
        if u1 > u2:
            return None
    return x1 + u1 * dx, y1 + u1 * dy, x1 + u2 * dx, y1 + u2 * dy


def _mapper(rect: SourceRect, target: tuple[float, float, float, float]):
    tx, ty, tw, th = target
    scale = min(tw / rect.width, th / rect.height)
    ox = tx + (tw - rect.width * scale) / 2
    oy = ty + (th - rect.height * scale) / 2

    def point(x: float, y_top: float) -> tuple[float, float]:
        return ox + (x - rect.x0) * scale, oy + (rect.y1 - y_top) * scale

    return point, scale


def _header(c: canvas.Canvas, metadata: dict[str, str]) -> None:
    x, y, w, h = 20, PAGE_H - 82, PAGE_W - 40, 62
    c.setStrokeColor(black)
    c.setLineWidth(0.7)
    c.rect(x, y, w, h, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 14, "Croqui")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x + 5, y + 39, "RGE")
    c.setFont("Helvetica-Oblique", 5.5)
    c.drawString(x + 38, y + 43, "RioGrandeEnergia")
    c.line(x + 5, y + 31, x + w - 5, y + 31)
    c.line(x + 5, y + 16, x + w - 5, y + 16)

    fields = [
        ("Departamento:", metadata.get("departamento", "")),
        ("Municipio:", metadata.get("municipio", "")),
        ("Equipamento:", metadata.get("equipamento", "")),
        ("Data do Levantamento:", metadata.get("data", metadata.get("data_levantamento", ""))),
        ("Levantamento de campo realizado por:", metadata.get("responsavel", "")),
    ]
    columns = [(x + 5, 150), (x + 285, 190), (x + 595, 160)]
    for index, (label, value) in enumerate(fields[:3]):
        fx, fw = columns[index]
        c.setFont("Helvetica-Bold", 5.5)
        c.drawString(fx, y + 21, label)
        c.setFont("Helvetica", 5.5)
        c.drawCentredString(fx + fw * 0.67, y + 21, str(value)[:42])
    c.setFont("Helvetica-Bold", 5.5)
    c.drawString(x + 5, y + 5, fields[3][0])
    c.setFont("Helvetica", 5.5)
    c.drawString(x + 155, y + 5, str(fields[3][1]))
    c.setFont("Helvetica-Bold", 5.5)
    c.drawString(x + 285, y + 5, fields[4][0])
    c.setFont("Helvetica", 5.5)
    c.drawString(x + 505, y + 5, str(fields[4][1])[:45])


def _footer(c: canvas.Canvas) -> None:
    x, y, w = 20, 20, PAGE_W - 40
    row_h = 5.7
    questions = [
        "Foi realizada a avaliacao do TIPO DE SOLO para permitir executar esta Obra?",
        "Foi realizada uma AVALIACAO EM CAMPO do Poste ou dos Equipamentos?",
        "Foi realizada uma AVALIACAO EM CAMPO para verificar a compatibilidade dos condutores?",
        "Caso seja necessario uma PREPARACAO para execucao da Obra, ela ja foi realizada?",
        "Existe VEICULO RESERVA no dia do deslocamento, caso necessite?",
        "Se a execucao afetar o CLIENTE, ele concorda com a intervencao?",
        "O MATERIAL para esta obra esta disponivel?",
        "O tempo para execucao esta adequado e evita atrasos?",
        "Esta previsto outro DOCUMENTO RESERVA para esta obra?",
        "Este documento ja foi CANCELADO ou e uma Reprogramacao?",
    ]
    c.setFillColor(HexColor("#ffff8a"))
    c.rect(x, y + len(questions) * row_h, w, 9, fill=1, stroke=1)
    c.setFillColor(red)
    c.setFont("Helvetica-Bold", 5)
    c.drawCentredString(x + w / 2, y + len(questions) * row_h + 2.5, "Avaliacao de Viabilidade - preenchimento obrigatorio")
    for index, question in enumerate(questions):
        ry = y + (len(questions) - index - 1) * row_h
        c.setFillColor(white if index % 2 == 0 else LIGHT_GRAY)
        c.rect(x, ry, w, row_h, fill=1, stroke=0)
        c.setFillColor(black)
        c.setFont("Helvetica", 4.3)
        c.drawString(x + 2, ry + 1.4, question)
        # Answers are project data. They remain blank until the source provides
        # them instead of being silently copied to every generated croqui.
    c.rect(x, y, w, len(questions) * row_h + 9, fill=0, stroke=1)


def _draw_pole(c: canvas.Canvas, x: float, y: float) -> None:
    c.setStrokeColor(black)
    c.setLineWidth(0.55)
    c.circle(x, y, 3.1, fill=0, stroke=1)
    c.circle(x, y, 1.25, fill=0, stroke=1)


def _draw_transformer(c: canvas.Canvas, x: float, y: float, code: str, *, new: bool = False) -> None:
    color = ORANGE if new else black
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(0.75)
    side = -1 if x > 440 else 1
    bx = x + side * 10
    c.line(x, y, bx, y)
    c.line(bx, y, bx - side * 5, y + 8)
    c.line(bx - side * 5, y + 8, bx - side * 10, y)
    c.line(bx - side * 10, y, bx, y)
    c.setFont("Helvetica", 5.2)
    label_x = bx - side * 2
    if side < 0:
        label_x -= 38
    c.drawString(label_x, y - 8, code)


def _draw_switch(c: canvas.Canvas, x: float, y: float, code: str) -> None:
    c.setStrokeColor(black)
    c.setFillColor(black)
    c.setLineWidth(0.7)
    c.line(x, y, x, y + 12)
    c.circle(x, y + 13.5, 1.2, fill=0, stroke=1)
    c.line(x, y + 15, x + 5, y + 22)
    c.circle(x + 5.8, y + 23, 1.2, fill=0, stroke=1)
    c.setFont("Helvetica", 5.2)
    c.drawString(x + 6, y + 5, code)


def _merge_metadata(extraction: ProjectExtraction, projeto: dict) -> dict[str, str]:
    metadata = {
        "departamento": extraction.metadata.get("departamento", ""),
        "municipio": extraction.metadata.get("municipio", ""),
        "equipamento": extraction.metadata.get("equipamento", ""),
        "data": extraction.metadata.get("data", ""),
        "responsavel": extraction.metadata.get("responsavel", ""),
    }
    meta = projeto.get("meta", {}) if isinstance(projeto, dict) else {}
    for key in ("departamento", "municipio", "equipamento", "data_levantamento", "responsavel"):
        value = str(meta.get(key, "")).strip()
        if not value:
            continue
        if key == "equipamento" and not _numeric_code(value):
            continue
        target_key = "data" if key == "data_levantamento" else key
        metadata[target_key] = value
    return metadata


def _draw_area_shape(
    c: canvas.Canvas,
    style: WorkAreaStyle,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> None:
    c.setStrokeColor(style.color)
    c.setLineWidth(1.4)
    c.setDash([2, 2])
    if style.shape == "ellipse":
        c.ellipse(x0, y0, x1, y1, fill=0, stroke=1)
    else:
        c.rect(x0, y0, x1 - x0, y1 - y0, fill=0, stroke=1)
    c.setDash([])


def _draw_area_overlay(
    c: canvas.Canvas,
    area: WorkArea,
    extraction: ProjectExtraction,
    point,
) -> None:
    if not area.positions:
        return
    mapped = [
        point(position.x, _page_y(position, extraction))
        for position in area.positions
    ]
    xs = [mapped_point[0] for mapped_point in mapped]
    ys = [mapped_point[1] for mapped_point in mapped]
    if len(mapped) == 1:
        half_width = 24.0 if area.kind != "LV" else 30.0
        half_height = 34.0 if area.kind != "LV" else 22.0
        x0, x1 = xs[0] - half_width, xs[0] + half_width
        y0, y1 = ys[0] - half_height, ys[0] + half_height
    else:
        x0, x1 = min(xs) - 12.0, max(xs) + 12.0
        y0, y1 = min(ys) - 12.0, max(ys) + 12.0
        if x1 - x0 < 48.0:
            delta = (48.0 - (x1 - x0)) / 2
            x0, x1 = x0 - delta, x1 + delta
        if y1 - y0 < 44.0:
            delta = (44.0 - (y1 - y0)) / 2
            y0, y1 = y0 - delta, y1 + delta
    _draw_area_shape(c, _area_style(area.kind), x0, y0, x1, y1)


def _wrap_text(text: str, font: str, size: float, max_width: float) -> list[str]:
    words = re.sub(r"\s+", " ", text.strip()).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and stringWidth(candidate, font, size) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_area_legend(
    c: canvas.Canvas,
    areas: list[WorkArea],
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    if not areas:
        return
    row_height = min(78.0, height / len(areas))
    top = y + height
    sample_width = min(64.0, width * 0.34)
    text_x = x + sample_width + 10.0
    text_width = max(45.0, width - sample_width - 12.0)
    for offset, area in enumerate(areas):
        row_top = top - offset * row_height
        center_y = row_top - row_height / 2
        if area.kind == "LV":
            shape_height = min(30.0, row_height * 0.42)
        else:
            shape_height = min(48.0, row_height * 0.64)
        _draw_area_shape(
            c,
            _area_style(area.kind),
            x,
            center_y - shape_height / 2,
            x + sample_width,
            center_y + shape_height / 2,
        )

        c.setFillColor(_area_style(area.kind).color)
        c.setFont("Helvetica-Bold", 5.5)
        label_lines = _wrap_text(area.label, "Helvetica-Bold", 5.5, text_width)[:2]
        text_y = center_y + 7.0
        for line in label_lines:
            c.drawString(text_x, text_y, line)
            text_y -= 7.0
        if area.observation:
            c.setFillColor(black)
            c.setFont("Helvetica", 5.0)
            for line in _wrap_text(area.observation, "Helvetica", 5.0, text_width)[:3]:
                c.drawString(text_x, text_y - 1.0, line)
                text_y -= 6.0


def render_croqui_geometrico(extraction: ProjectExtraction, projeto: dict, out_path: Path) -> Path:
    """Gera o croqui usando exclusivamente coordenadas extraidas do PDF."""

    if not extraction.conductors:
        raise ValueError("Projeto sem condutores CAD azuis ou verdes")
    page_no = _choose_page(extraction, projeto)
    work_areas = _resolve_work_areas(extraction, projeto, page_no)
    area_positions = tuple(
        position for area in work_areas for position in area.positions
    )
    anchors = _choose_anchors(
        extraction, projeto, page_no, extra_positions=area_positions
    )
    region = _source_region(extraction, page_no, anchors)
    legend_width = 215.0 if work_areas else 0.0
    target = (28.0, 98.0, PAGE_W - 56.0 - legend_width, 405.0)
    point, scale = _mapper(region, target)
    metadata = _merge_metadata(extraction, projeto)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle("Croqui")
    _header(c, metadata)
    _footer(c)
    c.setStrokeColor(black)
    c.rect(20, 20, PAGE_W - 40, PAGE_H - 40, fill=0, stroke=1)

    for segment in extraction.conductors:
        if segment.page != page_no:
            continue
        clipped = _clip_line(region, segment.x1, segment.y1, segment.x2, segment.y2)
        if clipped is None:
            continue
        x1, y1, x2, y2 = clipped
        ox1, oy1 = point(x1, y1)
        ox2, oy2 = point(x2, y2)
        c.setStrokeColor(black)
        c.setLineWidth(max(0.45, min(1.0, scale * 0.8)))
        c.setDash([] if segment.tensao == "MT" else [3, 2])
        c.line(ox1, oy1, ox2, oy2)
    c.setDash([])

    for pole in extraction.poles:
        if pole.position.page != page_no:
            continue
        y_top = _page_y(pole.position, extraction)
        if region.x0 <= pole.position.x <= region.x1 and region.y0 <= y_top <= region.y1:
            px, py = point(pole.position.x, y_top)
            _draw_pole(c, px, py)

    rendered_codes: set[str] = set()
    for equipment in _all_equipment(extraction):
        if equipment.position.page != page_no or equipment.numero in rendered_codes:
            continue
        y_top = _page_y(equipment.position, extraction)
        if not (region.x0 <= equipment.position.x <= region.x1 and region.y0 <= y_top <= region.y1):
            continue
        x, y = point(equipment.position.x, y_top)
        context = getattr(equipment, "contexto", "").upper()
        is_new = bool(getattr(equipment, "novo", False) or "INSTALAR" in context or "NOVO" in context)
        if isinstance(equipment, Transformer):
            _draw_transformer(c, x, y, equipment.numero, new=is_new)
        elif equipment.tipo == "RELIGADOR" or equipment.tipo == "CHAVE":
            _draw_switch(c, x, y, equipment.numero)
        else:
            c.setFont("Helvetica", 5)
            c.setFillColor(black)
            c.drawString(x + 4, y + 4, equipment.numero)
        rendered_codes.add(equipment.numero)

    for area in work_areas:
        _draw_area_overlay(c, area, extraction, point)

    if work_areas:
        legend_x = target[0] + target[2] + 14.0
        _draw_area_legend(
            c,
            work_areas,
            legend_x,
            target[1] + 12.0,
            PAGE_W - legend_x - 24.0,
            target[3] - 24.0,
        )

    c.save()
    return out_path
