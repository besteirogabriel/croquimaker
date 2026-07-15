from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from pydantic import Field

from croqui_engine.core.models import Equipment, SerializableModel, TechnicalPayload
from croqui_engine.output.contract import (
    make_equipment_label,
    normalize_equipment_code,
    normalize_equipment_type,
    parse_equipment_label,
)


class EquipmentCandidateEvidence(SerializableModel):
    kind: str
    weight: float
    source: str
    detail: str | None = None
    bbox: dict[str, float] | None = None


class EquipmentCandidate(SerializableModel):
    equipment_type: str
    code: str
    label: str
    confidence: float
    evidence: list[EquipmentCandidateEvidence] = Field(default_factory=list)
    bbox: dict[str, float] | None = None
    source: str = "unresolved"

    @property
    def score(self) -> float:
        return self.confidence


def resolve_main_equipment(
    payload: TechnicalPayload,
    source_pdf_path: Path | None = None,
    equipment: list[Equipment] | None = None,
) -> EquipmentCandidate | None:
    candidates = resolve_equipment_candidates(payload, source_pdf_path=source_pdf_path, equipment=equipment)
    return candidates[0] if candidates else None


def resolve_equipment_candidates(
    payload: TechnicalPayload,
    source_pdf_path: Path | None = None,
    equipment: list[Equipment] | None = None,
) -> list[EquipmentCandidate]:
    equipment = equipment if equipment is not None else payload.active_equipment()
    builder = _CandidateBuilder()

    for item in equipment:
        code = normalize_equipment_code(item.code)
        eq_type = normalize_equipment_type(item.type)
        if not code or not eq_type:
            continue
        builder.ensure(eq_type, code, item.bbox.as_dict() if item.bbox else None)
        builder.add(
            eq_type,
            code,
            "equipment_table",
            0.08,
            "parsed_equipment",
            detail=item.raw_text or f"{item.type} {item.code}",
            bbox=item.bbox.as_dict() if item.bbox else None,
        )
        if item.node_id:
            builder.add(
                eq_type,
                code,
                "topology_position",
                0.05,
                "graph_association",
                detail=f"associated_node={item.node_id}",
            )

    _add_execution_plan_evidence(builder, payload)
    _add_header_text_evidence(builder, payload)
    _add_filename_evidence(builder, source_pdf_path)
    _add_work_zone_evidence(builder, payload)
    _add_symbol_evidence(builder, payload)
    _add_visual_frequency_evidence(builder, payload)
    _add_spatial_fallback_evidence(builder, payload)

    return builder.candidates()


class _CandidateBuilder:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], dict[str, Any]] = {}

    def ensure(self, equipment_type: str | None, code: str | None, bbox: dict[str, Any] | None = None) -> None:
        eq_type = normalize_equipment_type(equipment_type)
        normalized_code = normalize_equipment_code(code)
        if not eq_type or not normalized_code:
            return
        key = (eq_type, normalized_code)
        self._items.setdefault(
            key,
            {
                "equipment_type": eq_type,
                "code": normalized_code,
                "bbox": _clean_bbox(bbox),
                "evidence": [],
            },
        )
        if bbox and not self._items[key].get("bbox"):
            self._items[key]["bbox"] = _clean_bbox(bbox)

    def add(
        self,
        equipment_type: str | None,
        code: str | None,
        kind: str,
        weight: float,
        source: str,
        detail: str | None = None,
        bbox: dict[str, Any] | None = None,
    ) -> None:
        eq_type = normalize_equipment_type(equipment_type)
        normalized_code = normalize_equipment_code(code)
        if not eq_type or not normalized_code or weight <= 0:
            return
        self.ensure(eq_type, normalized_code, bbox)
        evidence = EquipmentCandidateEvidence(
            kind=kind,
            weight=round(weight, 4),
            source=source,
            detail=detail,
            bbox=_clean_bbox(bbox),
        )
        self._items[(eq_type, normalized_code)]["evidence"].append(evidence)

    def candidates(self) -> list[EquipmentCandidate]:
        output: list[EquipmentCandidate] = []
        for item in self._items.values():
            evidence = _dedupe_evidence(item["evidence"])
            score = _score_evidence(evidence)
            if not evidence:
                continue
            source = evidence[0].kind if evidence else "unresolved"
            label = make_equipment_label(item["equipment_type"], item["code"])
            output.append(
                EquipmentCandidate(
                    equipment_type=item["equipment_type"],
                    code=item["code"],
                    label=label,
                    confidence=score,
                    evidence=evidence,
                    bbox=item.get("bbox"),
                    source=source,
                )
            )
        return sorted(
            output,
            key=lambda candidate: (
                candidate.confidence,
                _source_rank(candidate.source),
                len(candidate.evidence),
            ),
            reverse=True,
        )


def _add_execution_plan_evidence(builder: _CandidateBuilder, payload: TechnicalPayload) -> None:
    actions = payload.meta.get("tes_actions") or []
    for action in actions:
        code = normalize_equipment_code(str(action.get("code") or ""))
        eq_type = normalize_equipment_type(str(action.get("label") or action.get("type") or ""))
        if not code or not eq_type:
            continue
        status = str(action.get("status") or "").lower()
        if status in {"abrir", "fechar"}:
            weight = 0.35
        elif status in {"instalar", "retirar", "remover"}:
            weight = 0.28
        else:
            weight = 0.16
        builder.add(
            eq_type,
            code,
            "execution_plan",
            weight,
            "tes_actions",
            detail=str(action.get("raw_text") or status or ""),
        )

    main = payload.meta.get("main_switching_equipment")
    eq_type, code = parse_equipment_label(str(main) if main else None)
    if eq_type and code:
        builder.add(
            eq_type,
            code,
            "execution_plan_selected",
            0.22,
            "main_switching_equipment",
            detail=str(main),
        )


def _add_header_text_evidence(builder: _CandidateBuilder, payload: TechnicalPayload) -> None:
    for key in (
        "header_equipment",
        "project_header_equipment",
        "equipment_header",
        "selected_header_equipment",
    ):
        eq_type, code = parse_equipment_label(str(payload.meta.get(key) or ""))
        if eq_type and code:
            builder.add(eq_type, code, "header_text", 0.18, key, detail=str(payload.meta.get(key)))

    header_text = " ".join(
        str(payload.meta.get(key) or "")
        for key in ("project_header_text", "raw_header_text", "service_description")
    )
    for eq_type, code in _equipment_labels_from_text(header_text):
        builder.add(eq_type, code, "header_text", 0.12, "project_text", detail=header_text[:160])


def _add_filename_evidence(builder: _CandidateBuilder, source_pdf_path: Path | None) -> None:
    if not source_pdf_path:
        return
    names = [source_pdf_path.name]
    original_name = source_pdf_path.parent / "original_filename.txt"
    if original_name.exists():
        try:
            names.append(original_name.read_text(encoding="utf-8").strip())
        except Exception:
            pass
    for name in names:
        for eq_type, code in _equipment_labels_from_text(name):
            builder.add(eq_type, code, "input_filename", 0.10, "source_filename", detail=name)


def _add_work_zone_evidence(builder: _CandidateBuilder, payload: TechnicalPayload) -> None:
    trace = payload.meta.get("project_vector_trace") or {}
    labels = _label_positions(payload)
    red_points = _red_points(trace)
    cluster = _dominant_cluster(red_points)
    if not cluster:
        return
    cx = sum(point[0] for point in cluster) / len(cluster)
    cy = sum(point[1] for point in cluster) / len(cluster)
    for (eq_type, code), label in labels.items():
        distance = math.hypot(label[0] - cx, label[1] - cy)
        if distance > 420:
            continue
        weight = max(0.04, 0.18 * (1 - distance / 420))
        builder.add(
            eq_type,
            code,
            "near_work_zone",
            weight,
            "red_intervention_area",
            detail=f"distance={distance:.1f}",
            bbox=_label_bbox(payload, code),
        )


def _add_symbol_evidence(builder: _CandidateBuilder, payload: TechnicalPayload) -> None:
    trace = payload.meta.get("project_vector_trace") or {}
    labels = _label_positions(payload)
    symbols = [
        (float(item.get("x") or 0), float(item.get("y") or 0))
        for item in trace.get("symbols") or []
        if item.get("x") is not None and item.get("y") is not None
    ]
    if not symbols:
        return
    for (eq_type, code), point in labels.items():
        nearest = min((math.hypot(point[0] - sx, point[1] - sy) for sx, sy in symbols), default=999999.0)
        if nearest <= 55:
            builder.add(
                eq_type,
                code,
                "compatible_symbol",
                0.08,
                "nearby_vector_symbol",
                detail=f"distance={nearest:.1f}",
                bbox=_label_bbox(payload, code),
            )


def _add_visual_frequency_evidence(builder: _CandidateBuilder, payload: TechnicalPayload) -> None:
    labels = [str(value) for value in payload.meta.get("project_numeric_labels") or []]
    raw_text = " ".join(
        str(value or "")
        for key, value in payload.meta.items()
        if key in {"service_description", "execution_conditions", "switching_plan", "switching_steps"}
    )
    for equipment in payload.active_equipment():
        code = normalize_equipment_code(equipment.code)
        eq_type = normalize_equipment_type(equipment.type)
        if not code or not eq_type:
            continue
        count = labels.count(code) + raw_text.count(code)
        if equipment.raw_text and code in equipment.raw_text:
            count += 1
        if count:
            builder.add(
                eq_type,
                code,
                "frequency_visual",
                min(0.06, 0.02 * count),
                "numeric_labels",
                detail=f"count={count}",
            )


def _add_spatial_fallback_evidence(builder: _CandidateBuilder, payload: TechnicalPayload) -> None:
    trace = payload.meta.get("project_vector_trace") or {}
    labels = _label_positions(payload)
    red_points = _red_points(trace)
    cluster = _dominant_cluster(red_points)
    if not cluster or not labels:
        return
    cx = sum(point[0] for point in cluster) / len(cluster)
    cy = sum(point[1] for point in cluster) / len(cluster)
    ranked = []
    for (eq_type, code), point in labels.items():
        distance = math.hypot(point[0] - cx, point[1] - cy)
        priority = 0 if eq_type == "TR" and distance <= 260 else 1
        ranked.append((priority, distance, eq_type, code))
    if not ranked:
        return
    _, distance, eq_type, code = sorted(ranked, key=lambda row: (row[0], row[1]))[0]
    builder.add(
        eq_type,
        code,
        "spatial_fallback",
        0.08,
        "legacy_red_cluster_heuristic",
        detail=f"distance={distance:.1f}",
        bbox=_label_bbox(payload, code),
    )


def _equipment_labels_from_text(text: str) -> list[tuple[str, str]]:
    output = []
    for match in re.finditer(r"\b(TR|FU|FC|CF|RL|SC)\s*(\d{3,8})\b", text or "", flags=re.IGNORECASE):
        eq_type = normalize_equipment_type(match.group(1))
        code = normalize_equipment_code(match.group(2))
        if eq_type and code:
            output.append((eq_type, code))
    return output


def _label_positions(payload: TechnicalPayload) -> dict[tuple[str, str], tuple[float, float]]:
    by_code = {
        equipment.code: normalize_equipment_type(equipment.type)
        for equipment in payload.active_equipment()
        if equipment.code
    }
    labels: dict[tuple[str, str], tuple[float, float]] = {}
    for item in [
        *(payload.meta.get("project_vector_trace") or {}).get("labels", []),
        *(payload.meta.get("project_numeric_label_positions") or []),
    ]:
        code = normalize_equipment_code(str(item.get("text") or ""))
        eq_type = by_code.get(code or "")
        if not code or not eq_type:
            continue
        try:
            labels[(eq_type, code)] = (float(item["x"]), float(item["y"]))
        except Exception:
            continue
    return labels


def _label_bbox(payload: TechnicalPayload, code: str) -> dict[str, float] | None:
    for item in payload.meta.get("project_numeric_label_positions") or []:
        if normalize_equipment_code(str(item.get("text") or "")) != code:
            continue
        bbox = item.get("bbox")
        if bbox:
            return _clean_bbox(bbox)
    return None


def _red_points(trace: dict) -> list[tuple[float, float]]:
    return [
        point
        for segment in trace.get("segments") or []
        if segment.get("kind") == "red"
        for point in (
            (float(segment["x1"]), float(segment["y1"])),
            (float(segment["x2"]), float(segment["y2"])),
        )
    ]


def _dominant_cluster(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
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
    return clusters[0] if clusters else []


def _dedupe_evidence(items: list[EquipmentCandidateEvidence]) -> list[EquipmentCandidateEvidence]:
    by_kind: dict[str, EquipmentCandidateEvidence] = {}
    for item in items:
        current = by_kind.get(item.kind)
        if not current or item.weight > current.weight:
            by_kind[item.kind] = item
    return sorted(by_kind.values(), key=lambda item: (_source_rank(item.kind), item.weight), reverse=True)


def _score_evidence(evidence: list[EquipmentCandidateEvidence]) -> float:
    total = sum(item.weight for item in evidence)
    kinds = {item.kind for item in evidence}
    if kinds <= {"equipment_table", "frequency_visual"}:
        total = min(total, 0.24)
    if kinds <= {"near_work_zone", "spatial_fallback", "frequency_visual"}:
        total = min(total, 0.38)
    if "execution_plan" in kinds and len(kinds) >= 3:
        total += 0.06
    if "header_text" in kinds and len(kinds) >= 3:
        total += 0.04
    return round(max(0.0, min(total, 0.98)), 4)


def _source_rank(source: str) -> int:
    order = {
        "execution_plan": 90,
        "execution_plan_selected": 82,
        "header_text": 76,
        "input_filename": 66,
        "equipment_table": 56,
        "near_work_zone": 50,
        "compatible_symbol": 44,
        "topology_position": 38,
        "frequency_visual": 30,
        "spatial_fallback": 10,
    }
    return order.get(source, 0)


def _clean_bbox(bbox: dict[str, Any] | None) -> dict[str, float] | None:
    if not bbox:
        return None
    try:
        return {
            "x0": float(bbox["x0"]),
            "y0": float(bbox["y0"]),
            "x1": float(bbox["x1"]),
            "y1": float(bbox["y1"]),
        }
    except Exception:
        return None
