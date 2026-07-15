from __future__ import annotations

from pathlib import Path

from croqui_engine.core.models import TechnicalPayload
from croqui_engine.corpus.registry import load_registry


def select_corpus_xls_template(payload: TechnicalPayload) -> Path | None:
    try:
        registry = load_registry()
    except FileNotFoundError:
        return None

    case_id = str(payload.meta.get("corpus_case_id") or "")
    if case_id:
        case = registry.case_map().get(case_id)
        if case and case.target_croqui_xls:
            return Path(case.target_croqui_xls.path)

    expected_type = _equipment_type(payload)
    if expected_type:
        for case in registry.cases:
            if case.equipment_type_from_name == expected_type and case.target_croqui_xls:
                return Path(case.target_croqui_xls.path)

    for case in registry.cases:
        if case.target_croqui_xls:
            return Path(case.target_croqui_xls.path)
    return None


def _equipment_type(payload: TechnicalPayload) -> str | None:
    for key in ("corpus_equipment_type", "equipment_type", "main_equipment_type"):
        value = str(payload.meta.get(key) or "").upper().strip()
        if value:
            return "FC" if value == "CF" else value
    for equipment in payload.active_equipment():
        value = equipment.type.upper()
        if "TRANSFORMADOR" in value or value == "TR":
            return "TR"
        if "FUSIVEL" in value or "FUSÍVEL" in value or value == "FU":
            return "FU"
        if "COMANDO" in value or "FACA" in value or value in {"FC", "CF"}:
            return "FC"
        if "RELIGADOR" in value or value == "RL":
            return "RL"
    return None
