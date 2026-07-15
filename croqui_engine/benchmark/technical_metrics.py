from __future__ import annotations

from croqui_engine.core.models import TechnicalPayload
from croqui_engine.corpus.models import GoldenCase


def compare_technical(case: GoldenCase, payload: TechnicalPayload) -> dict:
    expected_type = case.equipment_type_from_name
    expected_code = case.equipment_code_from_name
    active_equipment = payload.active_equipment()
    codes = {item.code for item in active_equipment}
    types = {_normalize_type(item.type) for item in active_equipment}
    type_ok = _expected_type_ok(expected_type, types) if expected_type else None
    code_ok = expected_code in codes if expected_code else None
    equipment_score = 0.0
    parts = []
    if type_ok is not None:
        parts.append(1.0 if type_ok else 0.0)
    if code_ok is not None:
        parts.append(1.0 if code_ok else 0.0)
    if active_equipment:
        parts.append(1.0)
    equipment_score = sum(parts) / len(parts) if parts else 0.0
    return {
        "equipment_score": round(equipment_score, 4),
        "expected_type": expected_type,
        "expected_code": expected_code,
        "detected_types": sorted(types),
        "detected_codes": sorted(codes)[:50],
        "type_ok": type_ok,
        "code_ok": code_ok,
        "equipment_count": len(active_equipment),
        "span_count": len(payload.active_spans()),
        "node_count": len(payload.active_nodes()),
    }


def _normalize_type(value: str) -> str:
    upper = (value or "").upper()
    if "TRANSFORMADOR" in upper or upper == "TR":
        return "TR"
    if "FUSIVEL" in upper or "FUSÍVEL" in upper or upper == "FU":
        return "FU"
    if "COMANDO" in upper or "FACA" in upper or upper in {"FC", "CF"}:
        return "FC"
    if "RELIGADOR" in upper or upper == "RL":
        return "RL"
    return upper


def _expected_type_ok(expected: str | None, detected: set[str]) -> bool:
    if not expected:
        return False
    expected = "FC" if expected == "CF" else expected
    return expected in detected

