from __future__ import annotations

import re

from croqui_engine.core.models import (
    Equipment,
    ExtractedWord,
    MaterialItem,
    Node,
    Span,
    WorkArea,
)
from croqui_engine.parser.equipment_parser import (
    parse_equipment_from_text,
    parse_equipment_from_words,
)
from croqui_engine.parser.material_parser import parse_materials
from croqui_engine.parser.span_parser import (
    parse_nodes,
    parse_nodes_from_words,
    parse_spans,
    parse_spans_from_words,
)
from croqui_engine.parser.tes_parser import parse_tes_equipment


def parse_project_text(text: str, words: list[ExtractedWord] | None = None) -> dict:
    words = words or []

    nodes = _dedupe_nodes([*parse_nodes(text), *parse_nodes_from_words(words)])
    spans = _dedupe_spans([*parse_spans(text), *parse_spans_from_words(words)])
    equipment = _dedupe_equipment(
        [*parse_tes_equipment(text), *parse_equipment_from_text(text), *parse_equipment_from_words(words)]
    )
    materials = _dedupe_materials(parse_materials(text))
    work_areas = _infer_work_areas(text, spans)
    numeric_labels = _numeric_labels(text, words)
    numeric_label_positions = _numeric_label_positions(words)

    return {
        "nodes": nodes,
        "spans": spans,
        "equipment": equipment,
        "materials": materials,
        "work_areas": work_areas,
        "numeric_labels": numeric_labels,
        "numeric_label_positions": numeric_label_positions,
    }


def _dedupe_nodes(nodes: list[Node]) -> list[Node]:
    out: dict[str, Node] = {}
    for node in nodes:
        current = out.get(node.id)
        if not current or node.confidence > current.confidence:
            out[node.id] = node
    return sorted(out.values(), key=lambda n: int(n.id[1:]) if n.id[1:].isdigit() else 9999)


def _dedupe_spans(spans: list[Span]) -> list[Span]:
    out: dict[str, Span] = {}
    for span in spans:
        current = out.get(span.id)
        if not current or span.confidence > current.confidence:
            out[span.id] = span
    return sorted(out.values(), key=lambda s: (int(s.from_node[1:]), int(s.to_node[1:])))


def _dedupe_equipment(equipment: list[Equipment]) -> list[Equipment]:
    out: dict[tuple[str, str, str | None], Equipment] = {}
    for item in equipment:
        key = (item.code, item.type, item.status)
        current = out.get(key)
        if not current or item.confidence > current.confidence:
            out[key] = item
    return sorted(out.values(), key=lambda e: (e.type, e.code, e.status or ""))


def _dedupe_materials(materials: list[MaterialItem]) -> list[MaterialItem]:
    out: dict[str, MaterialItem] = {}
    for item in materials:
        out.setdefault(item.code, item)
    return sorted(out.values(), key=lambda m: m.code)


def _infer_work_areas(text: str, spans: list[Span]) -> list[WorkArea]:
    if not spans:
        return []
    lower = (text or "").lower()
    if "area de trabalho" not in lower and "área de trabalho" not in lower:
        return []
    pages = sorted({span.page_index for span in spans if span.page_index is not None})
    page_index = pages[0] if pages else 0
    return [WorkArea(id="WA-1", page_index=page_index, confidence=0.45, raw_text="Area de trabalho")]


def _numeric_labels(text: str, words: list[ExtractedWord]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    candidates = re.findall(r"\b\d{5,8}\b", text or "")
    candidates.extend(word.text for word in words if re.fullmatch(r"\d{5,8}", word.text))
    for value in candidates:
        if value not in seen:
            seen.add(value)
            labels.append(value)
    return labels


def _numeric_label_positions(words: list[ExtractedWord]) -> list[dict]:
    output: list[dict] = []
    seen: set[tuple[str, int, int, int]] = set()
    for word in words:
        value = word.text.strip()
        if not re.fullmatch(r"\d{5,8}", value):
            continue
        key = (value, word.page_index, int(word.bbox.x0), int(word.bbox.y0))
        if key in seen:
            continue
        seen.add(key)
        output.append(
            {
                "text": value,
                "page_index": word.page_index,
                "x": word.bbox.center[0],
                "y": word.bbox.center[1],
                "bbox": word.bbox.model_dump(mode="json"),
            }
        )
    return output
