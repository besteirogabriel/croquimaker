from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from reportlab.lib.colors import black, red, white, HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from croquimaker.core.schema import normalizar_viabilidade, viabilidade_automatica
from sistema.generation.equipment_scene import (
    EquipmentScene,
    SceneEquipment,
    resolve_equipment_scene,
)
from sistema.parsing.entities import ExistingEquipment, Position, ProjectExtraction, Transformer
from sistema.topology.network import NetworkSelection, select_service_network


PAGE_W, PAGE_H = landscape(A4)
LIGHT_GRAY = HexColor("#d7d7d7")


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


def _viability_percentage(answers: list[str]) -> str:
    """Match the RGE workbook formula: Sim answers in questions 1-8."""

    score = sum(answer == "Sim" for answer in answers[:8]) / 8 * 100
    return f"{score:.1f}%".replace(".", ",")


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


def _footer(c: canvas.Canvas, projeto: dict) -> None:
    x, y, w = 20, 20, PAGE_W - 40
    row_h = 5.7
    questions = [
        "Foi realizada a avaliação do TIPO DE SOLO para permitir executar esta Obra?",
        "Foi realizada uma AVALIAÇÃO EM CAMPO do Poste ou dos Equipamentos para realizar as Manobras?",
        "Foi realizada uma AVALIAÇÃO EM CAMPO para verificar a compatibilidade do condutor para Linha Viva?",
        "Caso seja necessária uma PREPARAÇÃO para execução da Obra, ela já foi realizada?",
        "Existe VEÍCULO RESERVA no dia do desligamento, caso necessite?",
        "Se a execução afetar o CLIENTE, ele concorda com a intervenção?",
        "O MATERIAL para esta obra está disponível?",
        "O tempo para execução está adequado e evita possibilidades de ATRASOS?",
        "Está previsto outro DOCUMENTO RESERVA para esta obra?",
        "Este documento já foi CANCELADO ou é uma Reprogramação?",
    ]
    viability = projeto.get("viabilidade", {}) if isinstance(projeto, dict) else {}
    viability_rows = (
        viability.get("respostas")
        if isinstance(viability, dict)
        else None
    )
    answers = (
        normalizar_viabilidade(viability_rows)
        if viability_rows
        else viabilidade_automatica()
    )
    percentage = _viability_percentage(answers)
    answer_x = x + w - 93
    c.setFillColor(HexColor("#ffff8a"))
    c.rect(x, y + len(questions) * row_h, w, 9, fill=1, stroke=1)
    c.setFillColor(red)
    c.setFont("Helvetica-Bold", 5)
    c.drawCentredString(
        x + w / 2,
        y + len(questions) * row_h + 2.5,
        "Avaliação de Viabilidade - preenchimento obrigatório",
    )
    c.drawRightString(
        x + w - 3,
        y + len(questions) * row_h + 2.5,
        f"Viabilidade: {percentage}",
    )
    for index, question in enumerate(questions):
        ry = y + (len(questions) - index - 1) * row_h
        c.setFillColor(white if index % 2 == 0 else LIGHT_GRAY)
        c.rect(x, ry, w, row_h, fill=1, stroke=0)
        c.setFillColor(black)
        c.setFont("Helvetica", 4.3)
        c.drawString(x + 2, ry + 1.4, question)
        c.setFont("Helvetica-Bold", 4.3)
        c.drawString(answer_x + 3, ry + 1.4, answers[index])
    c.setStrokeColor(black)
    c.setLineWidth(0.3)
    c.line(answer_x, y, answer_x, y + len(questions) * row_h)
    c.rect(x, y, w, len(questions) * row_h + 9, fill=0, stroke=1)


def _draw_pole(c: canvas.Canvas, x: float, y: float, *, new: bool = False) -> None:
    c.setStrokeColor(black)
    c.setFillColor(black)
    c.setLineWidth(0.55)
    if new:
        c.wedge(x - 2.55, y - 2.55, x + 2.55, y + 2.55, 90, 180, fill=1, stroke=0)
    c.circle(x, y, 3.1, fill=0, stroke=1)
    c.setFillColor(white)
    c.circle(x, y, 1.25, fill=0, stroke=1)
    c.setFillColor(black)


def _outward_vector(
    x: float,
    y: float,
    center: tuple[float, float],
    fallback_index: int,
) -> tuple[float, float]:
    dx = x - center[0]
    dy = y - center[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-6:
        directions = ((0.0, 1.0), (1.0, 0.0), (0.0, -1.0), (-1.0, 0.0))
        return directions[fallback_index % len(directions)]
    return dx / length, dy / length


def _draw_transformer_symbol(
    c: canvas.Canvas,
    x: float,
    y: float,
    dx: float,
    dy: float,
    *,
    new: bool,
    disconnected: bool,
) -> tuple[float, float]:
    px, py = -dy, dx
    apex = (x + dx * 4.1, y + dy * 4.1)
    base = (x + dx * 15.0, y + dy * 15.0)
    left = (base[0] + px * 5.2, base[1] + py * 5.2)
    right = (base[0] - px * 5.2, base[1] - py * 5.2)
    c.setLineWidth(0.75)
    path = c.beginPath()
    path.moveTo(*apex)
    path.lineTo(*left)
    path.lineTo(*right)
    path.close()
    c.drawPath(path, fill=1 if new else 0, stroke=1)
    if disconnected:
        cut_x = x + dx * 7.0
        cut_y = y + dy * 7.0
        c.setLineWidth(1.0)
        c.line(cut_x - px * 2.4, cut_y - py * 2.4, cut_x + px * 2.4, cut_y + py * 2.4)
    return x + dx * 23.0, y + dy * 23.0


def _draw_fuse_switch_symbol(
    c: canvas.Canvas,
    x: float,
    y: float,
    dx: float,
    dy: float,
    *,
    open_switch: bool,
) -> tuple[float, float]:
    px, py = -dy, dx
    hinge = (x + dx * 7.0, y + dy * 7.0)
    contact = (x + dx * 16.0, y + dy * 16.0)
    c.setLineWidth(0.8)
    c.line(x + dx * 4.0, y + dy * 4.0, *hinge)
    c.circle(*hinge, 1.25, fill=1, stroke=1)
    blade_end = (
        contact[0] + (px * 4.2 if open_switch else 0.0),
        contact[1] + (py * 4.2 if open_switch else 0.0),
    )
    c.line(*hinge, *blade_end)
    c.line(
        contact[0] - px * 3.0,
        contact[1] - py * 3.0,
        contact[0] + px * 3.0,
        contact[1] + py * 3.0,
    )
    c.line(
        contact[0] + dx * 2.5 - px * 2.3,
        contact[1] + dy * 2.5 - py * 2.3,
        contact[0] + dx * 2.5 + px * 2.3,
        contact[1] + dy * 2.5 + py * 2.3,
    )
    return x + dx * 25.0, y + dy * 25.0


def _draw_generic_equipment(
    c: canvas.Canvas,
    x: float,
    y: float,
    dx: float,
    dy: float,
) -> tuple[float, float]:
    cx = x + dx * 12.0
    cy = y + dy * 12.0
    c.setLineWidth(0.75)
    c.rect(cx - 3.2, cy - 3.2, 6.4, 6.4, fill=0, stroke=1)
    c.line(x + dx * 4.0, y + dy * 4.0, cx - dx * 3.2, cy - dy * 3.2)
    return x + dx * 21.0, y + dy * 21.0


def _draw_equipment(
    c: canvas.Canvas,
    equipment: SceneEquipment,
    x: float,
    y: float,
    center: tuple[float, float],
    fallback_index: int,
) -> None:
    dx, dy = _outward_vector(x, y, center, fallback_index)
    kind = equipment.kind.upper()
    state = equipment.state.upper()
    color = red if equipment.new or state in {"INSTALAR", "INCLUIR", "SUBSTITUIR"} else black
    c.setStrokeColor(color)
    c.setFillColor(color)
    if "TRANSFORMADOR" in kind:
        label_x, label_y = _draw_transformer_symbol(
            c,
            x,
            y,
            dx,
            dy,
            new=equipment.new or state in {"INSTALAR", "INCLUIR"},
            disconnected=state in {"ABRIR", "DESLIGAR"},
        )
    elif "FUS" in kind or "CHAVE" in kind:
        label_x, label_y = _draw_fuse_switch_symbol(
            c,
            x,
            y,
            dx,
            dy,
            open_switch=state in {"ABRIR", "DESLIGAR", "NA"},
        )
    else:
        label_x, label_y = _draw_generic_equipment(c, x, y, dx, dy)

    c.setFont("Helvetica", 5.3)
    if abs(dx) < 0.35:
        c.drawCentredString(label_x, label_y + (2.0 if dy >= 0 else -5.5), equipment.code)
    elif dx > 0:
        c.drawString(label_x + 2.0, label_y - 1.8, equipment.code)
    else:
        c.drawRightString(label_x - 2.0, label_y - 1.8, equipment.code)
    c.setStrokeColor(black)
    c.setFillColor(black)


def _draw_equipment_scene(
    c: canvas.Canvas,
    scene: EquipmentScene,
    extraction: ProjectExtraction,
    point,
) -> None:
    mapped_poles = {}
    for pole_index in {
        equipment.pole_index for equipment in scene.equipment
    }:
        pole = extraction.poles[pole_index]
        mapped_poles[pole_index] = point(
            pole.position.x,
            _page_y(pole.position, extraction),
        )
    if not mapped_poles:
        return
    center = (
        sum(value[0] for value in mapped_poles.values()) / len(mapped_poles),
        sum(value[1] for value in mapped_poles.values()) / len(mapped_poles),
    )
    counts: dict[int, int] = {}
    for equipment in scene.equipment:
        pole_x, pole_y = mapped_poles[equipment.pole_index]
        offset = counts.get(equipment.pole_index, 0)
        counts[equipment.pole_index] = offset + 1
        _draw_equipment(
            c,
            equipment,
            pole_x,
            pole_y,
            center,
            fallback_index=equipment.pole_index + offset,
        )


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


def _selection_region(
    extraction: ProjectExtraction,
    selection: NetworkSelection,
) -> SourceRect:
    points: list[tuple[float, float]] = []
    for segment_index, ranges in selection.segment_ranges.items():
        segment = extraction.conductors[segment_index]
        for t0, t1 in ranges:
            for t in (t0, t1):
                points.append(
                    (
                        segment.x1 + (segment.x2 - segment.x1) * t,
                        segment.y1 + (segment.y2 - segment.y1) * t,
                    )
                )
    height = extraction.page_sizes[selection.page][1]
    for pole_index in selection.pole_indexes:
        pole = extraction.poles[pole_index]
        points.append((pole.position.x, pole.position.y_pdf(height)))
    if not points:
        width, height = extraction.page_sizes[selection.page]
        return SourceRect(0.0, 0.0, width, height)

    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    span = max(max_x - min_x, max_y - min_y)
    page_scale = min(extraction.page_sizes[selection.page])
    margin = max(page_scale * 0.018, span * 0.055)
    return SourceRect(min_x - margin, min_y - margin, max_x + margin, max_y + margin)


def render_croqui_geometrico(
    extraction: ProjectExtraction,
    projeto: dict,
    out_path: Path,
    *,
    selection: NetworkSelection | None = None,
    selection_path: Path | None = None,
) -> Path:
    """Renderiza a rede CAD e os ativos comprovados do serviço."""

    if not extraction.conductors:
        raise ValueError("Projeto sem condutores CAD azuis ou verdes")
    page_no = _choose_page(extraction, projeto)
    selection = selection or select_service_network(extraction, projeto, page_no)
    if not selection.segment_ranges:
        raise ValueError("Nao foi possivel selecionar a rede relacionada ao servico")
    equipment_scene = resolve_equipment_scene(extraction, projeto, selection)
    region = _selection_region(extraction, selection)
    target = (28.0, 98.0, PAGE_W - 56.0, 405.0)
    point, scale = _mapper(region, target)
    metadata = _merge_metadata(extraction, projeto)

    if selection_path is not None:
        selection_path.parent.mkdir(parents=True, exist_ok=True)
        selection_payload = selection.to_dict(extraction)
        selection_payload["rendered_equipment"] = [
            asdict(item) for item in equipment_scene.equipment
        ]
        selection_payload["new_pole_indexes"] = sorted(
            equipment_scene.new_pole_indexes
        )
        selection_path.write_text(
            json.dumps(selection_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle("Croqui")
    _header(c, metadata)
    _footer(c, projeto)
    c.setStrokeColor(black)
    c.rect(20, 20, PAGE_W - 40, PAGE_H - 40, fill=0, stroke=1)

    for segment_index in sorted(selection.segment_ranges):
        segment = extraction.conductors[segment_index]
        for t0, t1 in selection.segment_ranges[segment_index]:
            x1 = segment.x1 + (segment.x2 - segment.x1) * t0
            y1 = segment.y1 + (segment.y2 - segment.y1) * t0
            x2 = segment.x1 + (segment.x2 - segment.x1) * t1
            y2 = segment.y1 + (segment.y2 - segment.y1) * t1
            ox1, oy1 = point(x1, y1)
            ox2, oy2 = point(x2, y2)
            c.setStrokeColor(black)
            c.setLineWidth(max(0.45, min(1.0, scale * 0.8)))
            # Simbologia RGE: rede secundaria (BT) continua e rede primaria
            # (MT) tracejada, conforme a planilha oficial de simbologia.
            c.setDash([2.2, 1.6] if segment.tensao == "MT" else [])
            c.line(ox1, oy1, ox2, oy2)
    c.setDash([])

    for pole_index in sorted(selection.pole_indexes):
        pole = extraction.poles[pole_index]
        y_top = _page_y(pole.position, extraction)
        px, py = point(pole.position.x, y_top)
        _draw_pole(
            c,
            px,
            py,
            new=pole_index in equipment_scene.new_pole_indexes,
        )

    _draw_equipment_scene(c, equipment_scene, extraction, point)

    c.save()
    return out_path
