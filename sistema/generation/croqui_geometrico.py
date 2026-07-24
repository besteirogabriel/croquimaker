from __future__ import annotations

import json
import math
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
from sistema.generation.rge_symbols import (
    draw_rge_symbol,
    load_rge_symbol_catalog,
    symbol_for_equipment,
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
    draw_rge_symbol(
        c,
        "POSTE_NOVO" if new else "POSTE_EXISTENTE",
        x,
        y,
    )


def _unit(dx: float, dy: float) -> tuple[float, float] | None:
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return None
    return dx / length, dy / length


def _incident_vectors(
    extraction: ProjectExtraction,
    selection: NetworkSelection,
    pole_index: int,
    point,
) -> list[tuple[float, float]]:
    pole = extraction.poles[pole_index]
    page_height = extraction.page_sizes[selection.page][1]
    pole_x = pole.position.x
    pole_y = pole.position.y_pdf(page_height)
    mapped_pole = point(pole_x, pole_y)
    directions: list[tuple[float, float]] = []
    attachment_tolerance = max(2.5, selection.graph.snap_tolerance * 2.0)

    for segment_index, ranges in selection.segment_ranges.items():
        segment = extraction.conductors[segment_index]
        if segment.page != selection.page:
            continue
        for t0, t1 in ranges:
            start = (
                segment.x1 + (segment.x2 - segment.x1) * t0,
                segment.y1 + (segment.y2 - segment.y1) * t0,
            )
            end = (
                segment.x1 + (segment.x2 - segment.x1) * t1,
                segment.y1 + (segment.y2 - segment.y1) * t1,
            )
            vx = end[0] - start[0]
            vy = end[1] - start[1]
            denominator = vx * vx + vy * vy
            if denominator <= 1e-9:
                continue
            position = (
                (pole_x - start[0]) * vx + (pole_y - start[1]) * vy
            ) / denominator
            position = max(0.0, min(1.0, position))
            nearest = (
                start[0] + vx * position,
                start[1] + vy * position,
            )
            if (
                math.hypot(nearest[0] - pole_x, nearest[1] - pole_y)
                > attachment_tolerance
            ):
                continue
            for endpoint in (start, end):
                if (
                    math.hypot(endpoint[0] - pole_x, endpoint[1] - pole_y)
                    <= attachment_tolerance
                ):
                    continue
                mapped = point(*endpoint)
                direction = _unit(
                    mapped[0] - mapped_pole[0],
                    mapped[1] - mapped_pole[1],
                )
                if direction is None:
                    continue
                if any(
                    direction[0] * current[0] + direction[1] * current[1] > 0.985
                    for current in directions
                ):
                    continue
                directions.append(direction)
    return directions


def _placement_direction(
    pole: tuple[float, float],
    center: tuple[float, float],
    incident: list[tuple[float, float]],
    *,
    right_bias: float = 0.0,
    conductor_penalty_weight: float = 3.0,
) -> tuple[float, float]:
    outward = _unit(pole[0] - center[0], pole[1] - center[1])

    # A simbologia da planilha trabalha ortogonalmente. Rotacionar os blocos
    # em passos de 22,5 graus fazia uma chave oficial parecer um ícone inventado.
    candidates = [
        (1.0, 0.0),
        (0.0, 1.0),
        (-1.0, 0.0),
        (0.0, -1.0),
    ]
    if right_bias > 0:
        candidates = [candidate for candidate in candidates if candidate[0] >= 0.35]
    opposite = None
    if incident:
        opposite = _unit(
            -sum(ray[0] for ray in incident),
            -sum(ray[1] for ray in incident),
        )

    def score(candidate: tuple[float, float]) -> float:
        conductor_penalty = sum(
            max(0.0, candidate[0] * ray[0] + candidate[1] * ray[1]) ** 2
            for ray in incident
        )
        outward_score = (
            candidate[0] * outward[0] + candidate[1] * outward[1]
            if outward is not None
            else 0.0
        )
        opposite_score = (
            candidate[0] * opposite[0] + candidate[1] * opposite[1]
            if opposite is not None
            else 0.0
        )
        return (
            -conductor_penalty_weight * conductor_penalty
            + 1.6 * outward_score
            + 0.55 * opposite_score
            + right_bias * candidate[0]
            + 0.01 * candidate[1]
        )

    return max(candidates, key=score)


def _cardinal(direction: tuple[float, float]) -> tuple[float, float]:
    dx, dy = direction
    if abs(dx) >= abs(dy):
        return (1.0 if dx >= 0 else -1.0, 0.0)
    return (0.0, 1.0 if dy >= 0 else -1.0)


def _equipment_direction(
    equipment: SceneEquipment,
    pole: tuple[float, float],
    center: tuple[float, float],
    incident: list[tuple[float, float]],
) -> tuple[float, float]:
    """Place workbook symbols by electrical topology, never by label position."""

    kind = equipment.kind.upper()
    if "TRANSFORMADOR" in kind:
        if len(incident) == 1:
            # At a terminal, the transformer lies on the network side of the
            # pole, as in the reference workbook.
            return _cardinal(incident[0])
        if len(incident) == 2 and incident[0][0] * incident[1][0] + incident[0][1] * incident[1][1] < -0.8:
            # On a straight corridor the RGE sheet convention keeps the
            # transformer on the left of vertical runs and below horizontal
            # runs. This is deterministic and independent of asset numbers.
            tangent = incident[0]
            return (
                (-1.0, 0.0)
                if abs(tangent[1]) >= abs(tangent[0])
                else (0.0, -1.0)
            )
    if "FUS" in kind and len(incident) == 1:
        ray = incident[0]
        return _cardinal((-ray[0], -ray[1]))
    return _placement_direction(
        pole,
        center,
        incident,
        conductor_penalty_weight=1.0 if "FUS" in kind else 3.0,
    )


def _draw_equipment(
    c: canvas.Canvas,
    equipment: SceneEquipment,
    x: float,
    y: float,
    direction: tuple[float, float],
) -> None:
    dx, dy = direction
    kind = equipment.kind.upper()
    state = equipment.state.upper()
    is_temporary_ground = kind in {"ATERRAMENTO_BT", "ATERRAMENTO_AT"}
    color = (
        red
        if (
            not is_temporary_ground
            and (
                equipment.new
                or state in {"INSTALAR", "INCLUIR", "SUBSTITUIR"}
            )
        )
        else black
    )
    symbol_name = symbol_for_equipment(kind)
    extent = (
        draw_rge_symbol(
            c,
            symbol_name,
            x,
            y,
            direction=direction,
            tint=color,
            # O Excel define o transformador como triângulo vazado. Instalação
            # muda a cor do traço, não o preenchimento da forma.
            fill_tint=False,
        )
        if symbol_name is not None
        else 0.0
    )
    label_x = x + dx * (extent + 3.0)
    label_y = y + dy * (extent + 3.0)

    # O desenho mostra apenas o identificador do ativo. A ação/estado continua
    # controlando a simbologia e a cor, mas não vira texto solto no croqui.
    label = equipment.code

    if label:
        c.setFont("Helvetica", 5.3)
        c.setFillColor(color)
        if abs(dx) < 0.35:
            c.drawCentredString(
                label_x,
                label_y + (2.0 if dy >= 0 else -5.5),
                label,
            )
        elif dx > 0:
            c.drawString(label_x + 2.0, label_y - 1.8, label)
        else:
            c.drawRightString(label_x - 2.0, label_y - 1.8, label)
    c.setStrokeColor(black)
    c.setFillColor(black)


def _resolve_equipment_directions(
    scene: EquipmentScene,
    extraction: ProjectExtraction,
    selection: NetworkSelection,
    point,
) -> list[tuple[SceneEquipment, tuple[float, float]]]:
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
        return []
    selected_poles = [
        extraction.poles[index]
        for index in selection.pole_indexes
        if extraction.poles[index].position.page == selection.page
    ]
    selected_points = [
        point(pole.position.x, _page_y(pole.position, extraction))
        for pole in selected_poles
    ]
    center = (
        (
            min(value[0] for value in selected_points)
            + max(value[0] for value in selected_points)
        )
        / 2,
        (
            min(value[1] for value in selected_points)
            + max(value[1] for value in selected_points)
        )
        / 2,
    )
    resolved: list[tuple[SceneEquipment, tuple[float, float]]] = []
    for equipment in scene.equipment:
        pole_x, pole_y = mapped_poles[equipment.pole_index]
        direction = _equipment_direction(
            equipment,
            (pole_x, pole_y),
            center,
            _incident_vectors(
                extraction,
                selection,
                equipment.pole_index,
                point,
            ),
        )
        resolved.append((equipment, direction))
    return resolved


def _render_equipment_scene(
    c: canvas.Canvas,
    resolved: list[tuple[SceneEquipment, tuple[float, float]]],
    extraction: ProjectExtraction,
    point,
) -> None:
    for equipment, direction in resolved:
        pole = extraction.poles[equipment.pole_index]
        pole_x, pole_y = point(
            pole.position.x,
            _page_y(pole.position, extraction),
        )
        _draw_equipment(c, equipment, pole_x, pole_y, direction)


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
    resolved_equipment = _resolve_equipment_directions(
        equipment_scene,
        extraction,
        selection,
        point,
    )
    metadata = _merge_metadata(extraction, projeto)

    if selection_path is not None:
        selection_path.parent.mkdir(parents=True, exist_ok=True)
        selection_payload = selection.to_dict(extraction)
        selection_payload["rendered_equipment"] = [
            {
                **asdict(item),
                "direction": list(direction),
            }
            for item, direction in resolved_equipment
        ]
        selection_payload["new_pole_indexes"] = sorted(
            equipment_scene.new_pole_indexes
        )
        selection_payload["symbol_catalog"] = load_rge_symbol_catalog()["source"]
        selection_payload["work_areas"] = []
        selection_payload["operational_notes"] = []
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

    _render_equipment_scene(c, resolved_equipment, extraction, point)

    c.save()
    return out_path
