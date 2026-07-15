from __future__ import annotations

from pathlib import Path

from croqui_engine.core.models import BBox
from croqui_engine.core.models_v2 import CroquiEntity, EvidenceRef


def extract_target_pdf(case_id: str, pdf_path: Path) -> dict:
    import fitz

    texts: list[CroquiEntity] = []
    lines: list[CroquiEntity] = []
    symbols: list[CroquiEntity] = []
    areas: list[CroquiEntity] = []
    page_size = (0.0, 0.0)
    header_fields: dict[str, str] = {}
    viability_table: dict = {}

    with fitz.open(pdf_path) as doc:
        if not doc:
            return {
                "page_size": page_size,
                "header_fields": header_fields,
                "viability_table": viability_table,
                "texts": texts,
                "lines": lines,
                "symbols": symbols,
                "areas": areas,
            }
        page = doc[0]
        page_size = (float(page.rect.width), float(page.rect.height))
        words = page.get_text("words") or []
        for idx, word in enumerate(words):
            text = str(word[4]).strip()
            if not text:
                continue
            bbox = BBox(x0=float(word[0]), y0=float(word[1]), x1=float(word[2]), y1=float(word[3]))
            texts.append(
                CroquiEntity(
                    id=f"text-{idx}",
                    type="TEXT",
                    label=text,
                    bbox=bbox,
                    evidence=[
                        EvidenceRef(
                            source="TARGET_PDF",
                            case_id=case_id,
                            file_path=str(pdf_path),
                            page_index=0,
                            bbox=bbox,
                            text=text,
                        )
                    ],
                )
            )

        drawings = page.get_drawings() or []
        for idx, drawing in enumerate(drawings):
            rect = drawing.get("rect")
            bbox = None
            if rect is not None:
                bbox = BBox(x0=float(rect.x0), y0=float(rect.y0), x1=float(rect.x1), y1=float(rect.y1))
            style = {
                "color": _color(drawing.get("color")),
                "fill": _color(drawing.get("fill")),
                "width": drawing.get("width"),
                "dashes": str(drawing.get("dashes") or ""),
                "raw_type": drawing.get("type"),
            }
            entity = CroquiEntity(
                id=f"draw-{idx}",
                type=_drawing_type(drawing),
                bbox=bbox,
                geometry={"items_count": len(drawing.get("items") or [])},
                style=style,
                evidence=[
                    EvidenceRef(
                        source="TARGET_PDF",
                        case_id=case_id,
                        file_path=str(pdf_path),
                        page_index=0,
                        bbox=bbox,
                        confidence=0.9,
                    )
                ],
            )
            if entity.type in {"LINE", "POLYLINE", "CURVE"}:
                lines.append(entity)
            elif entity.type in {"RECT", "AREA"}:
                areas.append(entity)
            else:
                symbols.append(entity)

    header_fields = _infer_header(texts, page_size)
    viability_table = _infer_viability(texts, page_size)
    return {
        "page_size": page_size,
        "header_fields": header_fields,
        "viability_table": viability_table,
        "texts": texts,
        "lines": lines,
        "symbols": symbols,
        "areas": areas,
    }


def _drawing_type(drawing: dict) -> str:
    items = drawing.get("items") or []
    kinds = {item[0] for item in items if item}
    rect = drawing.get("rect")
    if "l" in kinds:
        return "LINE"
    if {"c", "qu"} & kinds:
        return "CURVE"
    if "re" in kinds:
        if rect and (abs((rect.x1 - rect.x0) - (rect.y1 - rect.y0)) < 4):
            return "SYMBOL"
        return "RECT"
    if len(items) > 1:
        return "POLYLINE"
    return "DRAWING"


def _color(value) -> list[float] | None:
    if not value:
        return None
    try:
        return [float(value[0]), float(value[1]), float(value[2])]
    except Exception:
        return None


def _infer_header(texts: list[CroquiEntity], page_size: tuple[float, float]) -> dict[str, str]:
    _, height = page_size
    top = [item.label or "" for item in texts if item.bbox and item.bbox.y0 < height * 0.25]
    joined = " ".join(top)
    fields: dict[str, str] = {"raw_header_text": joined[:2000]}
    for token in ("Departamento", "Municipio", "Município", "Equipamento", "Data", "Levantador"):
        if token.lower() in joined.lower():
            fields[token] = "present"
    return fields


def _infer_viability(texts: list[CroquiEntity], page_size: tuple[float, float]) -> dict:
    _, height = page_size
    bottom = [item.label or "" for item in texts if item.bbox and item.bbox.y0 > height * 0.68]
    joined = " ".join(bottom)
    return {
        "raw_text": joined[:3000],
        "has_avaliacao_viabilidade": "viabilidade" in joined.lower(),
        "text_count": len(bottom),
    }

