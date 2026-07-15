from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from croqui_engine.output.contract import CroquiOutputContract, make_equipment_label

MIN_FINAL_CONFIDENCE = 0.70


def validate_output_contract(
    contract: CroquiOutputContract,
    *,
    generated_pdf_header_equipment: str | None = None,
    generated_xls_header_equipment: str | None = None,
) -> CroquiOutputContract:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = list(contract.warnings or [])

    expected_label = contract.expected_or_selected_main_equipment or make_equipment_label(
        contract.selected_equipment_type,
        contract.selected_equipment_code,
    )
    header_equipment = contract.header.get("equipment") or ""

    if expected_label and header_equipment and _norm(header_equipment) != _norm(expected_label):
        errors.append(
            {
                "code": "HEADER_EQUIPMENT_MISMATCH",
                "expected": expected_label,
                "generated": header_equipment,
            }
        )

    if generated_pdf_header_equipment and generated_xls_header_equipment:
        if _norm(generated_pdf_header_equipment) != _norm(generated_xls_header_equipment):
            errors.append(
                {
                    "code": "PDF_XLS_EQUIPMENT_MISMATCH",
                    "pdf": generated_pdf_header_equipment,
                    "xls": generated_xls_header_equipment,
                }
            )

    if generated_pdf_header_equipment and expected_label:
        if _norm(generated_pdf_header_equipment) != _norm(expected_label):
            errors.append(
                {
                    "code": "PDF_HEADER_EQUIPMENT_MISMATCH",
                    "expected": expected_label,
                    "generated": generated_pdf_header_equipment,
                }
            )

    if generated_xls_header_equipment and expected_label:
        if _norm(generated_xls_header_equipment) != _norm(expected_label):
            errors.append(
                {
                    "code": "XLS_HEADER_EQUIPMENT_MISMATCH",
                    "expected": expected_label,
                    "generated": generated_xls_header_equipment,
                }
            )

    if contract.selected_equipment_code and contract.primary_focus_code:
        if contract.selected_equipment_code != contract.primary_focus_code:
            errors.append(
                {
                    "code": "PRIMARY_FOCUS_CODE_MISMATCH",
                    "selected": contract.selected_equipment_code,
                    "focus": contract.primary_focus_code,
                }
            )

    if contract.selected_equipment_confidence is None:
        errors.append({"code": "SELECTED_EQUIPMENT_CONFIDENCE_MISSING"})

    if contract.focus_confidence is None:
        errors.append({"code": "FOCUS_CONFIDENCE_MISSING"})

    if contract.selected_equipment_code and contract.included_codes:
        if contract.selected_equipment_code not in contract.included_codes:
            errors.append(
                {
                    "code": "PRIMARY_CODE_NOT_IN_FOCUS",
                    "selected": contract.selected_equipment_code,
                    "included_codes": contract.included_codes,
                }
            )

    if not contract.focus_validated:
        warnings.append({"code": "FOCUS_NOT_VALIDATED", "message": "Foco tecnico requer revisao."})

    selected_confidence = float(contract.selected_equipment_confidence or 0)
    focus_confidence = float(contract.focus_confidence or 0)
    if selected_confidence < MIN_FINAL_CONFIDENCE:
        warnings.append(
            {
                "code": "LOW_SELECTED_EQUIPMENT_CONFIDENCE",
                "confidence": round(selected_confidence, 4),
            }
        )
    if focus_confidence < MIN_FINAL_CONFIDENCE:
        warnings.append({"code": "LOW_FOCUS_CONFIDENCE", "confidence": round(focus_confidence, 4)})

    contract.blocking_errors = _dedupe_messages(errors)
    contract.warnings = _dedupe_messages(warnings)
    if contract.blocking_errors:
        contract.validation_status = "BLOCKED"
        contract.output_status = "blocked"
        contract.final_output_allowed = False
    elif (
        selected_confidence >= MIN_FINAL_CONFIDENCE
        and focus_confidence >= MIN_FINAL_CONFIDENCE
        and contract.focus_validated
    ):
        contract.validation_status = "PASSED"
        contract.output_status = "final_candidate"
        contract.final_output_allowed = True
    else:
        contract.validation_status = "DRAFT_REVIEW_REQUIRED"
        contract.output_status = "draft"
        contract.final_output_allowed = False
    return contract


def build_output_validation_report(
    contract: CroquiOutputContract,
    *,
    generated_pdf_header_equipment: str | None = None,
    generated_xls_header_equipment: str | None = None,
) -> dict[str, Any]:
    return {
        "contract": {
            "project_id": contract.project_id,
            "expected_or_selected_main_equipment": contract.expected_or_selected_main_equipment,
            "selected_equipment_type": contract.selected_equipment_type,
            "selected_equipment_code": contract.selected_equipment_code,
            "selected_equipment_source": contract.selected_equipment_source,
            "selected_equipment_confidence": contract.selected_equipment_confidence,
            "primary_focus_code": contract.primary_focus_code,
            "focus_confidence": contract.focus_confidence,
            "focus_validated": contract.focus_validated,
        },
        "generated": {
            "pdf_header_equipment": generated_pdf_header_equipment,
            "xls_header_equipment": generated_xls_header_equipment,
            "primary_focus_code": contract.primary_focus_code,
            "visible_codes": contract.included_codes,
            "excluded_codes": contract.excluded_codes,
        },
        "validation": {
            "status": contract.validation_status,
            "output_status": contract.output_status,
            "final_output_allowed": contract.final_output_allowed,
            "blocking_errors": contract.blocking_errors,
            "warnings": contract.warnings,
        },
    }


def write_output_validation_report(
    contract: CroquiOutputContract,
    output_path: Path,
    *,
    generated_pdf_header_equipment: str | None = None,
    generated_xls_header_equipment: str | None = None,
) -> Path:
    report = build_output_validation_report(
        contract,
        generated_pdf_header_equipment=generated_pdf_header_equipment,
        generated_xls_header_equipment=generated_xls_header_equipment,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _norm(value: str) -> str:
    return " ".join(str(value or "").upper().split())


def _dedupe_messages(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    output = []
    for item in items:
        key = (str(item.get("code") or ""), json.dumps(item, sort_keys=True, ensure_ascii=False))
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output
