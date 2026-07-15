from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import Field

from croqui_engine.core.models import BBox, SerializableModel, TechnicalPayload

TYPE_ALIASES = {
    "TRANSFORMADOR": "TR",
    "TR": "TR",
    "CHAVE_FUSIVEL": "FU",
    "CHAVE_FUSÍVEL": "FU",
    "FUSIVEL": "FU",
    "FUSÍVEL": "FU",
    "FU": "FU",
    "CHAVE_COMANDO": "FC",
    "CHAVE FACA": "FC",
    "FACA": "FC",
    "FC": "FC",
    "CF": "FC",
    "RELIGADOR": "RL",
    "RL": "RL",
    "SECCIONALIZADORA": "SC",
    "SC": "SC",
}


class CroquiOutputContract(SerializableModel):
    contract_version: str = "v1-output-contract"
    project_id: str | None = None
    source_pdf: str | None = None
    header: dict[str, str] = Field(default_factory=dict)

    expected_or_selected_main_equipment: str | None = None
    selected_equipment_type: str | None = None
    selected_equipment_code: str | None = None
    selected_equipment_source: str | None = None
    selected_equipment_confidence: float | None = None
    selected_equipment_evidence: list[dict[str, Any]] = Field(default_factory=list)

    primary_focus_code: str | None = None
    primary_focus_bbox: dict[str, float] | None = None
    focus_region: dict[str, float] | None = None
    focus_confidence: float | None = None
    focus_validated: bool = False
    focus_evidence: list[dict[str, Any]] = Field(default_factory=list)

    included_codes: list[str] = Field(default_factory=list)
    excluded_codes: list[str] = Field(default_factory=list)

    output_status: str = "draft"
    validation_status: str = "DRAFT_REVIEW_REQUIRED"
    blocking_errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    final_output_allowed: bool = False


def output_contract_from_payload(payload: TechnicalPayload) -> CroquiOutputContract | None:
    raw = payload.meta.get("output_contract")
    if not raw:
        return None
    if isinstance(raw, CroquiOutputContract):
        return raw
    try:
        return CroquiOutputContract.model_validate(raw)
    except Exception:
        return None


def attach_output_contract(payload: TechnicalPayload, contract: CroquiOutputContract) -> TechnicalPayload:
    payload.meta["output_contract"] = contract.as_dict()
    payload.meta["main_switching_equipment"] = contract.expected_or_selected_main_equipment or ""
    payload.meta["selected_equipment_type"] = contract.selected_equipment_type or ""
    payload.meta["selected_equipment_code"] = contract.selected_equipment_code or ""
    payload.meta["selected_equipment_confidence"] = contract.selected_equipment_confidence
    payload.meta["primary_focus_code"] = contract.primary_focus_code or ""
    payload.meta["focus_confidence"] = contract.focus_confidence
    payload.meta["output_status"] = contract.output_status
    payload.meta["validation_status"] = contract.validation_status
    payload.meta["final_output_allowed"] = contract.final_output_allowed
    return payload


def normalize_equipment_type(value: str | None) -> str | None:
    if not value:
        return None
    upper = _strip_accents(str(value)).upper().replace("-", "_").replace(" ", "_")
    if upper in TYPE_ALIASES:
        return TYPE_ALIASES[upper]
    if "TRANSFORMADOR" in upper:
        return "TR"
    if "FUSIVEL" in upper:
        return "FU"
    if "COMANDO" in upper or "FACA" in upper:
        return "FC"
    if "RELIGADOR" in upper:
        return "RL"
    if "SECCIONALIZADORA" in upper:
        return "SC"
    return upper[:3] if upper else None


def make_equipment_label(equipment_type: str | None, code: str | None) -> str:
    normalized_type = normalize_equipment_type(equipment_type)
    normalized_code = normalize_equipment_code(code)
    if normalized_type and normalized_code:
        return f"{normalized_type} {normalized_code}"
    return normalized_code or normalized_type or ""


def normalize_equipment_code(value: str | None) -> str | None:
    if value is None:
        return None
    found = re.findall(r"\b\d{3,8}\b", str(value))
    return found[0] if found else None


def parse_equipment_label(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    text = str(value).upper()
    code = normalize_equipment_code(text)
    type_match = re.search(r"\b(TR|FU|FC|CF|RL|SC)\b", text)
    eq_type = normalize_equipment_type(type_match.group(1)) if type_match else None
    if not eq_type:
        for token in TYPE_ALIASES:
            if token in _strip_accents(text).replace(" ", "_"):
                eq_type = normalize_equipment_type(token)
                break
    return eq_type, code


def bbox_to_dict(bbox: BBox | dict[str, Any] | None) -> dict[str, float] | None:
    if bbox is None:
        return None
    raw = bbox.as_dict() if isinstance(bbox, BBox) else bbox
    try:
        return {
            "x0": float(raw["x0"]),
            "y0": float(raw["y0"]),
            "x1": float(raw["x1"]),
            "y1": float(raw["y1"]),
        }
    except Exception:
        return None


def region_from_points(
    points: list[tuple[float, float]],
    padding: float = 120.0,
    page_width: float | None = None,
    page_height: float | None = None,
) -> dict[str, float] | None:
    if not points:
        return None
    x0 = min(point[0] for point in points) - padding
    y0 = min(point[1] for point in points) - padding
    x1 = max(point[0] for point in points) + padding
    y1 = max(point[1] for point in points) + padding
    if page_width is not None:
        x0 = max(0.0, x0)
        x1 = min(float(page_width), x1)
    if page_height is not None:
        y0 = max(0.0, y0)
        y1 = min(float(page_height), y1)
    return {"x0": round(x0, 3), "y0": round(y0, 3), "x1": round(x1, 3), "y1": round(y1, 3)}


def output_header_values(
    payload: TechnicalPayload,
    equipment_label: str | None = None,
) -> dict[str, str]:
    contract = output_contract_from_payload(payload)
    if contract and contract.header:
        header = dict(contract.header)
        if equipment_label and not header.get("equipment"):
            header["equipment"] = equipment_label
        return header

    equipment = equipment_label or main_equipment_label_from_payload(payload)
    return {
        "department": str(payload.meta.get("department") or ""),
        "municipality": str(payload.meta.get("municipality") or "").upper(),
        "equipment": equipment,
        "survey_date": str(payload.meta.get("survey_date") or ""),
        "surveyor": str(payload.meta.get("surveyor") or payload.meta.get("levantador") or ""),
    }


def main_equipment_label_from_payload(payload: TechnicalPayload) -> str:
    contract = output_contract_from_payload(payload)
    if contract and contract.expected_or_selected_main_equipment:
        return contract.expected_or_selected_main_equipment

    raw_label = payload.meta.get("main_switching_equipment")
    if raw_label:
        eq_type, code = parse_equipment_label(str(raw_label))
        return make_equipment_label(eq_type, code) or str(raw_label)

    for equipment in payload.active_equipment():
        label = make_equipment_label(equipment.type, equipment.code)
        if label:
            return label
    return ""


def selected_equipment_code_from_payload(payload: TechnicalPayload) -> str:
    contract = output_contract_from_payload(payload)
    if contract and contract.selected_equipment_code:
        return contract.selected_equipment_code
    _, code = parse_equipment_label(payload.meta.get("main_switching_equipment"))
    if code:
        return code
    for equipment in payload.active_equipment():
        if equipment.code:
            return equipment.code
    return ""


def build_contract_header(payload: TechnicalPayload, equipment_label: str) -> dict[str, str]:
    header = output_header_values(payload, equipment_label)
    header["department"] = _first_non_empty(
        header.get("department"),
        payload.meta.get("department"),
        payload.meta.get("department_name"),
        "JOBEL",
    )
    header["municipality"] = _first_non_empty(
        header.get("municipality"),
        payload.meta.get("municipality"),
        "MUNICIPIO NAO IDENTIFICADO",
    ).upper()
    header["equipment"] = equipment_label or "EQUIPAMENTO NAO IDENTIFICADO"
    header["survey_date"] = _first_non_empty(
        header.get("survey_date"),
        payload.meta.get("survey_date"),
        _date_from_processed_at(payload.meta.get("processed_at")),
        "DATA NAO IDENTIFICADA",
    )
    header["surveyor"] = _first_non_empty(
        header.get("surveyor"),
        payload.meta.get("surveyor"),
        payload.meta.get("levantador"),
        payload.meta.get("responsible"),
        payload.meta.get("executor"),
        "RESPONSAVEL NAO IDENTIFICADO",
    )
    return header


def contract_header_warnings(header: dict[str, str]) -> list[dict[str, str]]:
    warnings = []
    fallbacks = {
        "department": "JOBEL",
        "municipality": "MUNICIPIO NAO IDENTIFICADO",
        "equipment": "EQUIPAMENTO NAO IDENTIFICADO",
        "survey_date": "DATA NAO IDENTIFICADA",
        "surveyor": "RESPONSAVEL NAO IDENTIFICADO",
    }
    for key, fallback in fallbacks.items():
        if header.get(key) == fallback:
            warnings.append({"code": "HEADER_FIELD_FALLBACK", "field": key, "value": fallback})
    return warnings


def source_pdf_display_name(source_pdf: Path | None) -> str | None:
    if source_pdf is None:
        return None
    return str(source_pdf)


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _date_from_processed_at(value: Any) -> str:
    text = str(value or "")
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{day}/{month}/{year}"


def _strip_accents(value: str) -> str:
    table = str.maketrans(
        "ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç",
        "AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuc",
    )
    return value.translate(table)
