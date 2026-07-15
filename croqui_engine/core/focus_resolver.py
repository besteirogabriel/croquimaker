from __future__ import annotations

import math
from typing import Any

from pydantic import Field

from croqui_engine.core.equipment_candidate_resolver import EquipmentCandidate
from croqui_engine.core.models import SerializableModel, TechnicalPayload
from croqui_engine.output.contract import normalize_equipment_code, region_from_points


class FocusResolution(SerializableModel):
    primary_focus_code: str | None = None
    primary_focus_bbox: dict[str, float] | None = None
    focus_region: dict[str, float] | None = None
    included_codes: list[str] = Field(default_factory=list)
    excluded_codes: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    focus_validated: bool = False
    evidence: list[dict[str, Any]] = Field(default_factory=list)


def resolve_focus(
    payload: TechnicalPayload,
    selected_candidate: EquipmentCandidate | None,
) -> FocusResolution:
    trace = payload.meta.get("project_vector_trace") or {}
    selected_code = selected_candidate.code if selected_candidate else ""
    page_width = float(trace.get("page_width") or 0) or None
    page_height = float(trace.get("page_height") or 0) or None

    labels = _labels(payload)
    red_points = _red_points(trace)
    selected_label = labels.get(selected_code)
    evidence: list[dict[str, Any]] = []
    anchor_points: list[tuple[float, float]] = []
    primary_bbox = None

    if selected_label:
        anchor_points.append((selected_label["x"], selected_label["y"]))
        primary_bbox = selected_label.get("bbox") or _bbox_around(selected_label["x"], selected_label["y"], 36)
        evidence.append({"kind": "selected_code_label", "weight": 0.30, "code": selected_code})

    candidate_bbox = selected_candidate.bbox if selected_candidate else None
    if candidate_bbox:
        cx = (float(candidate_bbox["x0"]) + float(candidate_bbox["x1"])) / 2
        cy = (float(candidate_bbox["y0"]) + float(candidate_bbox["y1"])) / 2
        anchor_points.append((cx, cy))
        primary_bbox = primary_bbox or candidate_bbox
        evidence.append({"kind": "selected_candidate_bbox", "weight": 0.20, "code": selected_code})

    if anchor_points:
        red_near = _nearby_points(anchor_points[0], red_points, radius=360)
        if red_near:
            anchor_points.extend(red_near)
            evidence.append({"kind": "near_work_zone", "weight": 0.16, "points": len(red_near)})
    else:
        cluster = _dominant_cluster(red_points)
        if cluster:
            anchor_points.extend(cluster)
            evidence.append({"kind": "red_zone_fallback", "weight": 0.10, "points": len(cluster)})

    if not anchor_points and labels:
        first = next(iter(labels.values()))
        anchor_points.append((first["x"], first["y"]))
        evidence.append({"kind": "label_fallback", "weight": 0.05})

    region = _focus_region(payload, trace, selected_code, anchor_points, page_width, page_height)
    included, excluded = _included_excluded_codes(labels, region)
    confidence = _focus_confidence(selected_candidate, selected_code, included, evidence, trace)
    focus_validated = bool(selected_code and selected_code in included and primary_bbox and confidence >= 0.55)

    return FocusResolution(
        primary_focus_code=selected_code or None,
        primary_focus_bbox=primary_bbox,
        focus_region=region,
        included_codes=included,
        excluded_codes=excluded,
        confidence=confidence,
        focus_validated=focus_validated,
        evidence=evidence,
    )


def _focus_region(
    payload: TechnicalPayload,
    trace: dict,
    selected_code: str,
    anchor_points: list[tuple[float, float]],
    page_width: float | None,
    page_height: float | None,
) -> dict[str, float] | None:
    if not anchor_points:
        return None

    points = list(anchor_points)
    labels = _labels(payload)
    selected_anchor = labels.get(selected_code)
    if selected_anchor:
        center = (selected_anchor["x"], selected_anchor["y"])
    else:
        center = (
            sum(point[0] for point in anchor_points) / len(anchor_points),
            sum(point[1] for point in anchor_points) / len(anchor_points),
        )

    for label in labels.values():
        point = (label["x"], label["y"])
        if math.hypot(point[0] - center[0], point[1] - center[1]) <= 520:
            points.append(point)

    for segment in trace.get("segments") or []:
        midpoint = (
            (float(segment["x1"]) + float(segment["x2"])) / 2,
            (float(segment["y1"]) + float(segment["y2"])) / 2,
        )
        if math.hypot(midpoint[0] - center[0], midpoint[1] - center[1]) <= 520:
            points.extend(
                [
                    (float(segment["x1"]), float(segment["y1"])),
                    (float(segment["x2"]), float(segment["y2"])),
                ]
            )

    return region_from_points(points, padding=80, page_width=page_width, page_height=page_height)


def _focus_confidence(
    selected_candidate: EquipmentCandidate | None,
    selected_code: str,
    included_codes: list[str],
    evidence: list[dict[str, Any]],
    trace: dict,
) -> float:
    score = 0.0
    if selected_candidate:
        score += min(float(selected_candidate.confidence or 0) * 0.45, 0.45)
    score += sum(float(item.get("weight") or 0) for item in evidence)
    if selected_code and selected_code in included_codes:
        score += 0.12
    if trace.get("mode") == "clean_project_trace" and not selected_code:
        score = min(score, 0.35)
    return round(max(0.0, min(score, 0.98)), 4)


def _labels(payload: TechnicalPayload) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in [
        *(payload.meta.get("project_vector_trace") or {}).get("labels", []),
        *(payload.meta.get("project_numeric_label_positions") or []),
    ]:
        code = normalize_equipment_code(str(item.get("text") or ""))
        if not code or code in output:
            continue
        try:
            x = float(item.get("x"))
            y = float(item.get("y"))
        except Exception:
            continue
        bbox = item.get("bbox")
        output[code] = {
            "code": code,
            "x": x,
            "y": y,
            "bbox": _clean_bbox(bbox) or _bbox_around(x, y, 24),
        }
    return output


def _included_excluded_codes(
    labels: dict[str, dict[str, Any]],
    region: dict[str, float] | None,
) -> tuple[list[str], list[str]]:
    if not region:
        return [], sorted(labels)
    included = []
    excluded = []
    for code, label in labels.items():
        inside = (
            region["x0"] <= label["x"] <= region["x1"]
            and region["y0"] <= label["y"] <= region["y1"]
        )
        (included if inside else excluded).append(code)
    return sorted(included), sorted(excluded)


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


def _nearby_points(
    center: tuple[float, float],
    points: list[tuple[float, float]],
    radius: float,
) -> list[tuple[float, float]]:
    return [point for point in points if math.hypot(point[0] - center[0], point[1] - center[1]) <= radius]


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


def _bbox_around(x: float, y: float, size: float) -> dict[str, float]:
    return {"x0": x - size, "y0": y - size, "x1": x + size, "y1": y + size}


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
