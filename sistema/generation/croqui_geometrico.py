from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.colors import black, red, white, HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

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
    """Renderiza somente condutores CAD e postes extraidos do PDF."""

    if not extraction.conductors:
        raise ValueError("Projeto sem condutores CAD azuis ou verdes")
    page_no = _choose_page(extraction, projeto)
    selection = selection or select_service_network(extraction, projeto, page_no)
    if not selection.segment_ranges:
        raise ValueError("Nao foi possivel selecionar a rede relacionada ao servico")
    region = _selection_region(extraction, selection)
    target = (28.0, 98.0, PAGE_W - 56.0, 405.0)
    point, scale = _mapper(region, target)
    metadata = _merge_metadata(extraction, projeto)

    if selection_path is not None:
        selection_path.parent.mkdir(parents=True, exist_ok=True)
        selection_path.write_text(
            json.dumps(selection.to_dict(extraction), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle("Croqui")
    _header(c, metadata)
    _footer(c)
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
            c.setDash([] if segment.tensao == "MT" else [2.2, 1.6])
            c.line(ox1, oy1, ox2, oy2)
    c.setDash([])

    for pole_index in sorted(selection.pole_indexes):
        pole = extraction.poles[pole_index]
        y_top = _page_y(pole.position, extraction)
        px, py = point(pole.position.x, y_top)
        _draw_pole(c, px, py)

    c.save()
    return out_path
