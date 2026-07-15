from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from croqui_engine.core.models import TechnicalPayload
from croqui_engine.output.contract import output_contract_from_payload
from croqui_engine.storage.database import Job
from croqui_engine.storage.file_store import job_output_dir


def validation_report_path(job_id: str) -> Path:
    return job_output_dir(job_id) / "output_validation_report.json"


def load_validation_report(job_id: str) -> dict[str, Any] | None:
    path = validation_report_path(job_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def output_summary(payload: TechnicalPayload, report: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = output_contract_from_payload(payload)
    validation = (report or {}).get("validation", {})
    generated = (report or {}).get("generated", {})
    if contract:
        return {
            "selected_main_equipment": contract.expected_or_selected_main_equipment or "",
            "selected_equipment_type": contract.selected_equipment_type or "",
            "selected_equipment_code": contract.selected_equipment_code or "",
            "selected_equipment_source": contract.selected_equipment_source or "",
            "selected_equipment_confidence": contract.selected_equipment_confidence,
            "primary_focus_code": contract.primary_focus_code or "",
            "focus_confidence": contract.focus_confidence,
            "output_status": contract.output_status,
            "validation_status": contract.validation_status,
            "final_output_allowed": contract.final_output_allowed,
            "warnings": contract.warnings,
            "blocking_errors": contract.blocking_errors,
            "pdf_header_equipment": generated.get("pdf_header_equipment"),
            "xls_header_equipment": generated.get("xls_header_equipment"),
        }

    return {
        "selected_main_equipment": payload.meta.get("main_switching_equipment", ""),
        "selected_equipment_type": payload.meta.get("selected_equipment_type", ""),
        "selected_equipment_code": payload.meta.get("selected_equipment_code", ""),
        "selected_equipment_source": "",
        "selected_equipment_confidence": payload.meta.get("selected_equipment_confidence"),
        "primary_focus_code": payload.meta.get("primary_focus_code", ""),
        "focus_confidence": payload.meta.get("focus_confidence"),
        "output_status": validation.get("output_status") or payload.meta.get("output_status", "draft"),
        "validation_status": validation.get("status")
        or payload.meta.get("validation_status", "DRAFT_REVIEW_REQUIRED"),
        "final_output_allowed": bool(
            validation.get("final_output_allowed", payload.meta.get("final_output_allowed", False))
        ),
        "warnings": validation.get("warnings", []),
        "blocking_errors": validation.get("blocking_errors", []),
        "pdf_header_equipment": generated.get("pdf_header_equipment"),
        "xls_header_equipment": generated.get("xls_header_equipment"),
    }


def artifact_paths(job: Job) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    raw = {
        "json": job.reviewed_payload_path or job.payload_path,
        "pdf": job.croqui_pdf_path,
        "png": job.croqui_png_path,
        "xls": job.excel_path,
        "report": str(validation_report_path(job.id)),
    }
    for kind, value in raw.items():
        path = Path(value) if value else None
        if path and path.is_file():
            paths[kind] = path
    return paths


def artifact_summary(job: Job) -> list[dict[str, str]]:
    return [
        {"kind": kind, "path": str(path), "filename": path.name}
        for kind, path in sorted(artifact_paths(job).items())
    ]
