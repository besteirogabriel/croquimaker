from __future__ import annotations

from typing import Any

from croqui_engine.output.contract import CroquiOutputContract


def validate_schematic_visual_quality(
    contract: CroquiOutputContract,
    layout: dict[str, Any] | None,
) -> CroquiOutputContract:
    report = visual_quality_report(layout, contract.primary_focus_code)
    contract.warnings = _append_unique_warnings(contract.warnings, report["warnings"])
    if report["status"] != "PASSED":
        contract.output_status = "low_quality_draft"
        contract.validation_status = (
            "BLOCKED" if contract.blocking_errors else "DRAFT_REVIEW_REQUIRED"
        )
        contract.final_output_allowed = False
    contract.header["visual_quality_status"] = report["status"]
    contract.header["visual_quality_score"] = str(report["score"])
    return contract


def _append_unique_warnings(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output = list(existing)
    seen = {tuple(sorted(item.items())) for item in output}
    for warning in incoming:
        key = tuple(sorted(warning.items()))
        if key in seen:
            continue
        output.append(warning)
        seen.add(key)
    return output


def visual_quality_report(layout: dict[str, Any] | None, focus_code: str | None) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    if not layout:
        return {
            "status": "FAILED",
            "score": 0.0,
            "warnings": [{"code": "SCHEMATIC_LAYOUT_MISSING"}],
        }
    if layout.get("source") != "SchematicLayoutEngine":
        warnings.append({"code": "NON_SCHEMATIC_LAYOUT_SOURCE", "source": layout.get("source")})

    nodes = layout.get("nodes") or []
    edges = layout.get("edges") or []
    labels = layout.get("labels") or []
    work_zones = layout.get("work_zones") or []
    canvas = layout.get("canvas") or {"width": 1000.0, "height": 420.0}
    width = float(canvas.get("width") or 1000.0)
    height = float(canvas.get("height") or 420.0)

    if len(nodes) < 1:
        warnings.append({"code": "SCHEMATIC_NODE_COUNT_LOW", "count": len(nodes)})
    if len(nodes) >= 2 and len(edges) < 1:
        warnings.append({"code": "SCHEMATIC_EDGE_COUNT_LOW", "count": len(edges)})

    small_labels = [
        label
        for label in labels
        if float(label.get("min_font_size") or 0) < 12.0 or not str(label.get("text") or "").strip()
    ]
    if small_labels:
        warnings.append({"code": "SCHEMATIC_LABELS_NOT_LEGIBLE", "count": len(small_labels)})

    occupancy = _occupancy(nodes, width, height)
    if occupancy < 0.12:
        warnings.append({"code": "SCHEMATIC_OCCUPANCY_TOO_SMALL", "occupancy": round(occupancy, 4)})
    if occupancy > 0.88:
        warnings.append({"code": "SCHEMATIC_OCCUPANCY_TOO_SPREAD", "occupancy": round(occupancy, 4)})

    focus_node = _focus_node(nodes, focus_code)
    if focus_node is None and focus_code:
        warnings.append({"code": "FOCUS_CODE_NOT_DRAWN", "focus_code": focus_code})
    elif focus_node is not None:
        centered = 0.22 * width <= float(focus_node.get("x") or 0) <= 0.78 * width
        if not centered:
            warnings.append({"code": "FOCUS_NOT_VISUALLY_CENTRAL", "focus_code": focus_code})
        if work_zones and _nearest_work_zone_distance(focus_node, work_zones) > 160:
            warnings.append({"code": "WORK_ZONE_FAR_FROM_FOCUS", "focus_code": focus_code})
        if not work_zones:
            warnings.append({"code": "WORK_ZONE_MISSING"})

    score = _score(warnings)
    return {
        "status": "PASSED" if not warnings else "FAILED",
        "score": round(score, 4),
        "warnings": warnings,
        "metrics": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "label_count": len(labels),
            "occupancy": round(occupancy, 4),
        },
    }


def _occupancy(nodes: list[dict[str, Any]], width: float, height: float) -> float:
    if not nodes:
        return 0.0
    xs = [float(node.get("x") or 0) for node in nodes]
    ys = [float(node.get("y") or 0) for node in nodes]
    box_w = max(xs) - min(xs)
    box_h = max(ys) - min(ys)
    return max(box_w / width, 0.05) * max(box_h / height, 0.05)


def _focus_node(nodes: list[dict[str, Any]], focus_code: str | None) -> dict[str, Any] | None:
    if focus_code:
        for node in nodes:
            if node.get("code") == focus_code:
                return node
    for node in nodes:
        if node.get("is_focus"):
            return node
    return None


def _nearest_work_zone_distance(focus_node: dict[str, Any], work_zones: list[dict[str, Any]]) -> float:
    fx = float(focus_node.get("x") or 0)
    fy = float(focus_node.get("y") or 0)
    distances = []
    for zone in work_zones:
        zx = float(zone.get("x") or 0)
        zy = float(zone.get("y") or 0)
        distances.append(((fx - zx) ** 2 + (fy - zy) ** 2) ** 0.5)
    return min(distances) if distances else 999999.0


def _score(warnings: list[dict[str, Any]]) -> float:
    penalties = {
        "SCHEMATIC_LAYOUT_MISSING": 1.0,
        "NON_SCHEMATIC_LAYOUT_SOURCE": 0.35,
        "SCHEMATIC_NODE_COUNT_LOW": 0.35,
        "SCHEMATIC_EDGE_COUNT_LOW": 0.25,
        "SCHEMATIC_LABELS_NOT_LEGIBLE": 0.25,
        "SCHEMATIC_OCCUPANCY_TOO_SMALL": 0.20,
        "SCHEMATIC_OCCUPANCY_TOO_SPREAD": 0.25,
        "FOCUS_CODE_NOT_DRAWN": 0.45,
        "FOCUS_NOT_VISUALLY_CENTRAL": 0.18,
        "WORK_ZONE_FAR_FROM_FOCUS": 0.25,
        "WORK_ZONE_MISSING": 0.18,
    }
    score = 1.0
    for warning in warnings:
        score -= penalties.get(str(warning.get("code") or ""), 0.10)
    return max(0.0, min(1.0, score))
